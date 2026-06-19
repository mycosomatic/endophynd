"""
Streaming alignment engine for targeted search — the heart of capability B.

Each target dataset is streamed (never landed whole) and piped *through* the
query, which acts as the reference (decision D05).  We keep only the records
that align.

Two interchangeable aligners:
  * minimap2 (default for genome/marker queries): emits SAM; we keep mapped
    records and read SEQ / NM to score them.
  * blastn   (default for rDNA queries): more sensitive to divergence; emits
    tabular hits including the aligned dataset sequence (``qseq``).

No database of the dataset is ever built or downloaded; the only thing that
indexes is the (tiny) query.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from endophynd.target.models import (
    Aligner,
    Hit,
    QuerySpec,
    Source,
    Target,
    TargetResult,
)

LOGAN_UNITIG_S3 = "s3://logan-pub/u/{acc}/{acc}.unitigs.fa.zst"

# FASTQ → FASTA on the fly (4-line records, unwrapped — true for fasterq-dump).
_FQ2FA = r"""awk 'NR%4==1{printf(">%s\n",substr($0,2))} NR%4==2{print}'"""

_CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")


# ---------------------------------------------------------------------------
# Stream command (dataset → stdout as FASTA/FASTQ)
# ---------------------------------------------------------------------------

def build_stream_command(target: Target, to_fasta: bool, threads: int = 4) -> str:
    """
    Shell snippet that writes the target's sequences to stdout.

    ``to_fasta`` converts FASTQ sources to FASTA (needed for blastn).  Logan
    unitigs and most local files are already FASTA, so conversion is a no-op
    there.
    """
    if target.source == Source.LOCAL:
        path = target.local_path or ""
        low = path.lower()
        if low.endswith(".zst"):
            base = f"zstdcat {path}"
        elif low.endswith(".gz"):
            base = f"gzip -dc {path}"
        else:
            base = f"cat {path}"
        # Convert only genuine FASTQ inputs.
        if to_fasta and (".fq" in low or ".fastq" in low):
            base = f"{base} | {_FQ2FA}"
        return base

    if target.source == Source.LOGAN:
        s3 = LOGAN_UNITIG_S3.format(acc=target.accession)
        # Unitigs are FASTA already; to_fasta is a no-op here.
        return f"aws s3 cp {s3} - --no-sign-request | zstdcat"

    if target.source == Source.SRA:
        # fasterq-dump streams interleaved FASTQ to stdout.
        base = (
            f"fasterq-dump --stdout --split-spot --threads {threads} "
            f"{target.accession}"
        )
        if to_fasta:
            base = f"{base} | {_FQ2FA}"
        return base

    raise ValueError(f"Unsupported source for streaming: {target.source}")


# ---------------------------------------------------------------------------
# Aligner command
# ---------------------------------------------------------------------------

def build_align_command(
    stream_cmd: str,
    aligner: Aligner,
    query: QuerySpec,
    *,
    threads: int = 4,
    minimap2_preset: str = "asm20",
    max_target_seqs: int = 5,
    evalue: float = 1e-5,
) -> str:
    """Full ``set -o pipefail`` shell pipeline: stream | aligner → stdout records."""
    if aligner == Aligner.MINIMAP2:
        mm = (
            f"minimap2 -ax {minimap2_preset} -t {threads} --secondary=no "
            f"{query.fasta_path} -"
        )
        # Drop unmapped records early when samtools is available.
        if shutil.which("samtools"):
            mm = f"{mm} | samtools view -F 4 -"
        return f"set -o pipefail; {stream_cmd} | {mm}"

    if aligner == Aligner.BLASTN:
        if not query.blast_db_prefix:
            raise ValueError("blastn selected but query BLAST DB was not built.")
        fields = "qseqid sseqid pident length qstart qend sstart send slen qseq"
        bn = (
            f"blastn -db {query.blast_db_prefix} -query /dev/stdin "
            f"-outfmt '6 {fields}' -num_threads {threads} "
            f"-max_target_seqs {max_target_seqs} -evalue {evalue}"
        )
        return f"set -o pipefail; {stream_cmd} | {bn}"

    raise ValueError(f"Unknown aligner: {aligner}")


# ---------------------------------------------------------------------------
# Parsers → Hit
# ---------------------------------------------------------------------------

def _cigar_stats(cigar: str) -> tuple[int, int]:
    """Return (ref_consumed, aln_block_len) from a CIGAR string."""
    ref_consumed = 0
    aln_block = 0
    for n, op in _CIGAR_RE.findall(cigar):
        n = int(n)
        if op in "MDN=X":
            ref_consumed += n
        if op in "MID=X":
            aln_block += n
    return ref_consumed, aln_block


def parse_minimap2_sam(
    lines, query: QuerySpec, *, min_identity: float, min_aln_len: int, min_query_cov: float
) -> list[Hit]:
    hits: list[Hit] = []
    for line in lines:
        if not line or line.startswith("@"):
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 11:
            continue
        flag = int(f[1])
        if flag & 0x4:            # unmapped
            continue
        if flag & 0x900:          # secondary / supplementary
            continue
        matched_seq_id = f[0]
        query_id = f[2]
        if query_id == "*":
            continue
        pos = int(f[3])
        cigar = f[5]
        seq = f[9]
        ref_consumed, aln_block = _cigar_stats(cigar)
        if aln_block == 0:
            continue
        # Edit distance from the NM tag.
        nm = None
        for tag in f[11:]:
            if tag.startswith("NM:i:"):
                nm = int(tag[5:])
                break
        if nm is None:
            continue
        identity = max(0.0, (aln_block - nm) / aln_block)
        qlen = query.record_lengths.get(query_id, 0)
        query_cov = (ref_consumed / qlen) if qlen else 0.0
        if identity < min_identity or aln_block < min_aln_len or query_cov < min_query_cov:
            continue
        hits.append(
            Hit(
                matched_seq_id=matched_seq_id,
                query_id=query_id,
                identity=identity,
                aln_len=aln_block,
                query_cov=query_cov,
                query_start=pos,
                query_end=pos + ref_consumed - 1,
                matched_seq="" if seq == "*" else seq,
                strand="-" if flag & 0x10 else "+",
            )
        )
    return hits


def parse_blastn_tab(
    lines, query: QuerySpec, *, min_identity: float, min_aln_len: int, min_query_cov: float
) -> list[Hit]:
    hits: list[Hit] = []
    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue
        f = line.split("\t")
        # qseqid sseqid pident length qstart qend sstart send slen qseq
        if len(f) < 10:
            continue
        matched_seq_id = f[0]
        query_id = f[1]
        identity = float(f[2]) / 100.0
        aln_len = int(f[3])
        sstart, send, slen = int(f[6]), int(f[7]), int(f[8])
        qseq = f[9].replace("-", "")
        query_cov = (abs(send - sstart) + 1) / slen if slen else 0.0
        strand = "-" if (send < sstart) else "+"
        if identity < min_identity or aln_len < min_aln_len or query_cov < min_query_cov:
            continue
        hits.append(
            Hit(
                matched_seq_id=matched_seq_id,
                query_id=query_id,
                identity=identity,
                aln_len=aln_len,
                query_cov=query_cov,
                query_start=min(sstart, send),
                query_end=max(sstart, send),
                matched_seq=qseq,
                strand=strand,
            )
        )
    return hits


# ---------------------------------------------------------------------------
# Run one target
# ---------------------------------------------------------------------------

def align_target(
    target: Target,
    query: QuerySpec,
    aligner: Aligner,
    *,
    threads: int = 4,
    minimap2_preset: str = "asm20",
    min_identity: float = 0.80,
    min_aln_len: int = 50,
    min_query_cov: float = 0.0,
    max_target_seqs: int = 5,
    evalue: float = 1e-5,
    log_path: Optional[str | Path] = None,
) -> TargetResult:
    """Stream one target through the query and return its filtered hits."""
    to_fasta = aligner == Aligner.BLASTN
    stream_cmd = build_stream_command(target, to_fasta, threads=threads)
    cmd = build_align_command(
        stream_cmd, aligner, query,
        threads=threads, minimap2_preset=minimap2_preset,
        max_target_seqs=max_target_seqs, evalue=evalue,
    )

    log_fh = open(log_path, "a") if log_path else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            cmd, shell=True, executable="/bin/bash",
            stdout=subprocess.PIPE, stderr=log_fh, text=True,
        )
        assert proc.stdout is not None
        if aligner == Aligner.MINIMAP2:
            hits = parse_minimap2_sam(
                proc.stdout, query,
                min_identity=min_identity, min_aln_len=min_aln_len,
                min_query_cov=min_query_cov,
            )
        else:
            hits = parse_blastn_tab(
                proc.stdout, query,
                min_identity=min_identity, min_aln_len=min_aln_len,
                min_query_cov=min_query_cov,
            )
        proc.stdout.close()
        rc = proc.wait()
    finally:
        if log_fh not in (subprocess.DEVNULL, None):
            log_fh.close()

    if rc != 0 and not hits:
        # Distinguish "Logan has no such accession" from a real failure where we can.
        status = "absent" if target.source == Source.LOGAN else "error"
        return TargetResult(
            accession=target.accession, source=target.source, status=status,
            hits=[], message=f"stream/aligner exited {rc}; see log.",
            bioproject=target.bioproject,
        )

    status = "ok" if hits else "empty"
    return TargetResult(
        accession=target.accession, source=target.source, status=status,
        hits=hits, bioproject=target.bioproject,
    )
