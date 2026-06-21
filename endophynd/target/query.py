"""
Prepare the query for targeted search and detect what kind of query it is.

Query type matters because of decision D20: Logan collapses the rDNA tandem
array to ~65 bp, so an rDNA/ITS query finds almost nothing in Logan unitigs and
must be run against SRA reads instead.  A whole-genome / single-copy-marker
query, by contrast, works well against Logan (RPB2 → 3389 bp unitigs, etc.).

So:
  * detect rDNA vs genome (auto, by aligning the query against the project's
    rDNA reference);
  * pick a default aligner (rDNA → blastn, genome → minimap2);
  * warn loudly when the query/source pairing is known to be weak.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from endophynd.target.models import Aligner, QuerySpec, QueryType, Source

DEFAULT_RDNA_REF = "resources/rdna_ref.fa"
# Fraction of total query bp that must align to the rDNA reference to call the
# query "rDNA".  Single-locus barcodes align almost end-to-end; a genome barely
# touches it (only its own rDNA copy).
_RDNA_COVERAGE_THRESHOLD = 0.40


# ---------------------------------------------------------------------------
# FASTA parsing (tiny, dependency-free)
# ---------------------------------------------------------------------------

def read_fasta_lengths(path: str | Path) -> dict[str, int]:
    """Return {record_id: length_bp} for a FASTA file. ID = first whitespace token."""
    lengths: dict[str, int] = {}
    current: str | None = None
    n = 0
    with open(path) as f:
        for line in f:
            if line.startswith(">"):
                if current is not None:
                    lengths[current] = n
                current = line[1:].strip().split()[0]
                n = 0
            else:
                n += len(line.strip())
    if current is not None:
        lengths[current] = n
    if not lengths:
        raise ValueError(f"No FASTA records found in query file: {path}")
    return lengths


# ---------------------------------------------------------------------------
# Query-type detection
# ---------------------------------------------------------------------------

def detect_query_type(
    query_path: str | Path,
    rdna_ref: str | Path = DEFAULT_RDNA_REF,
    total_query_bp: int | None = None,
) -> QueryType:
    """
    Decide whether the query is rDNA or a genome/marker by aligning it against
    the project's rDNA reference with blastn ``-subject`` (no DB build needed).

    Falls back to GENOME (with a warning) if blastn or the reference is missing.
    """
    rdna_ref = Path(rdna_ref)
    if not rdna_ref.exists():
        sys.stderr.write(
            f"[query][WARN] rDNA reference {rdna_ref} not found — cannot auto-detect "
            f"query type; assuming GENOME. Use --query-type to override.\n"
        )
        return QueryType.GENOME
    if shutil.which("blastn") is None:
        sys.stderr.write(
            "[query][WARN] blastn not on PATH — cannot auto-detect query type; "
            "assuming GENOME. Use --query-type to override.\n"
        )
        return QueryType.GENOME

    if total_query_bp is None:
        total_query_bp = sum(read_fasta_lengths(query_path).values())
    if total_query_bp == 0:
        return QueryType.GENOME

    # Per query record, collect non-overlapping covered intervals against rDNA ref.
    try:
        proc = subprocess.run(
            [
                "blastn",
                "-query", str(query_path),
                "-subject", str(rdna_ref),
                "-outfmt", "6 qseqid qstart qend",
                "-max_hsps", "50",
                "-evalue", "1e-5",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        sys.stderr.write(f"[query][WARN] query-type blastn failed ({e}); assuming GENOME.\n")
        return QueryType.GENOME

    intervals: dict[str, list[tuple[int, int]]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        qid, qs, qe = parts[0], int(parts[1]), int(parts[2])
        lo, hi = sorted((qs, qe))
        intervals.setdefault(qid, []).append((lo, hi))

    covered = sum(_merged_length(ivs) for ivs in intervals.values())
    frac = covered / total_query_bp
    qtype = QueryType.RDNA if frac >= _RDNA_COVERAGE_THRESHOLD else QueryType.GENOME
    sys.stderr.write(
        f"[query] auto-detected query type = {qtype.value} "
        f"({frac:.0%} of {total_query_bp} bp aligns to the rDNA reference).\n"
    )
    return qtype


def _merged_length(intervals: list[tuple[int, int]]) -> int:
    """Total length of the union of 1-based inclusive intervals."""
    if not intervals:
        return 0
    intervals = sorted(intervals)
    total = 0
    cur_lo, cur_hi = intervals[0]
    for lo, hi in intervals[1:]:
        if lo <= cur_hi + 1:
            cur_hi = max(cur_hi, hi)
        else:
            total += cur_hi - cur_lo + 1
            cur_lo, cur_hi = lo, hi
    total += cur_hi - cur_lo + 1
    return total


# ---------------------------------------------------------------------------
# Aligner selection + reference building
# ---------------------------------------------------------------------------

def choose_aligner(query_type: QueryType, requested: Aligner) -> Aligner:
    """Resolve AUTO aligner from the query type."""
    if requested != Aligner.AUTO:
        return requested
    return Aligner.BLASTN if query_type == QueryType.RDNA else Aligner.MINIMAP2


def build_blast_db(query_path: str | Path, workdir: str | Path) -> str:
    """makeblastdb on the query; returns the DB prefix."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    prefix = str(workdir / (Path(query_path).stem + ".querydb"))
    proc = subprocess.run(
        ["makeblastdb", "-in", str(query_path), "-dbtype", "nucl", "-out", prefix],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"makeblastdb failed:\n{proc.stderr}")
    return prefix


def prepare_query(
    query_path: str | Path,
    query_type: QueryType = QueryType.AUTO,
    aligner: Aligner = Aligner.AUTO,
    rdna_ref: str | Path = DEFAULT_RDNA_REF,
    workdir: str | Path | None = None,
) -> tuple[QuerySpec, Aligner]:
    """
    Read the query, resolve its type and the aligner, and build any aligner
    reference (a BLAST DB for blastn; minimap2 indexes the FASTA on the fly).
    """
    query_path = str(query_path)
    if not Path(query_path).exists():
        raise FileNotFoundError(f"Query file not found: {query_path}")

    lengths = read_fasta_lengths(query_path)
    total_bp = sum(lengths.values())

    resolved_type = (
        detect_query_type(query_path, rdna_ref, total_bp)
        if query_type == QueryType.AUTO
        else query_type
    )
    resolved_aligner = choose_aligner(resolved_type, aligner)

    spec = QuerySpec(
        fasta_path=query_path,
        query_type=resolved_type,
        record_lengths=lengths,
    )
    if resolved_aligner == Aligner.BLASTN and workdir is not None:
        spec.blast_db_prefix = build_blast_db(query_path, workdir)

    return spec, resolved_aligner


def pairing_warnings(query_type: QueryType, sources: set[Source]) -> list[str]:
    """
    Return human-readable warnings for query/source pairings known to be weak.

    The headline one (D20): an rDNA query against Logan unitigs will find only
    ~65 bp junction fragments because Logan collapses the rDNA tandem array.
    """
    warnings: list[str] = []
    if query_type == QueryType.RDNA and Source.LOGAN in sources:
        warnings.append(
            "rDNA/ITS query against Logan unitigs: Logan collapses the rDNA tandem "
            "array to ~65 bp (decision D20), so expect few/short hits. Use "
            "--source sra for rDNA queries."
        )
    if query_type == QueryType.GENOME and sources == {Source.SRA}:
        warnings.append(
            "Genome/marker query against SRA reads only: this works but streams far "
            "more data than Logan. If these accessions are in Logan, --source auto "
            "is cheaper."
        )
    return warnings
