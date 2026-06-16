#!/usr/bin/env python3
"""
Assign rDNA locus to baited unitigs via BLAST, then apply the informative-
length gate.  Outputs the same files as parse_itsx.py so the two scripts
are drop-in replacements in the annotate_and_gate rule.

Why BLAST instead of ITSx here:
  ITSx uses HMMER to locate SSU/LSU *flanking* anchors around the ITS region.
  Logan unitigs average ~200 bp — they contain ITS variable sequence but lack
  the conserved flanks, so ITSx detects nothing.  BLAST against a small per-
  locus reference assigns each fragment even without flanks.

Reference format (resources/rdna_ref.fa):
  Every sequence ID must begin with a locus prefix followed by an underscore:
    SSU_Fusarium_XR_014475154.1
    ITS_Alternaria_LC769425.1
    LSU_Agaricus_MF033200.1
  Build the reference with: python scripts/build_rdna_ref.py --email you@email

Outputs:
  --gated-out:   FASTA of reads that passed gate (FINE or COARSE)
  --gate-report: TSV  read_id, locus, informative_bp, gate_decision
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from endophynd.gate import GateDecision, GateEngine


def read_fasta(path: Path) -> dict[str, str]:
    seqs: dict[str, str] = {}
    hdr: str | None = None
    parts: list[str] = []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip()
            if line.startswith(">"):
                if hdr is not None:
                    seqs[hdr] = "".join(parts)
                hdr = line[1:].split()[0]
                parts = []
            elif hdr is not None:
                parts.append(line)
        if hdr is not None:
            seqs[hdr] = "".join(parts)
    return seqs


def build_blast_db(ref_fa: Path, db_dir: Path) -> Path:
    db_prefix = db_dir / "rdna"
    subprocess.run(
        [
            "makeblastdb",
            "-in", str(ref_fa),
            "-dbtype", "nucl",
            "-out", str(db_prefix),
            "-title", "endophynd_rdna_ref",
        ],
        check=True,
        capture_output=True,
    )
    return db_prefix


def run_blastn(
    query_fa: Path,
    db_prefix: Path,
    min_pident: float,
    evalue: float,
) -> dict[str, dict]:
    """
    Run blastn and return best hit per query.

    Returns {qseqid: {locus, informative_bp, pident}}
    """
    cmd = [
        "blastn",
        "-query", str(query_fa),
        "-db", str(db_prefix),
        # qseqid sseqid pident alignment_len query_len bitscore
        "-outfmt", "6 qseqid sseqid pident length qlen bitscore",
        "-perc_identity", str(min_pident),
        "-evalue", str(evalue),
        "-max_target_seqs", "10",
        "-max_hsps", "1",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    best: dict[str, dict] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        qid, sid, pident, alen, qlen, bitscore = parts
        pident_f = float(pident)
        bitscore_f = float(bitscore)
        locus = sid.split("_")[0]  # SSU, ITS, or LSU
        if qid not in best or bitscore_f > best[qid]["bitscore"]:
            best[qid] = {
                "locus": locus,
                "informative_bp": int(alen),
                "pident": pident_f,
                "bitscore": bitscore_f,
            }
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baited", required=True, help="Baited FASTA from retrieve_and_bait")
    ap.add_argument(
        "--rdna-ref", required=True,
        help="Per-locus rDNA reference FASTA (resources/rdna_ref.fa)",
    )
    ap.add_argument("--params", required=True, help="Path to params.yml")
    ap.add_argument("--gate-report", required=True)
    ap.add_argument("--gated-out", required=True)
    ap.add_argument("--min-pident", type=float, default=70.0,
                    help="Minimum BLAST percent identity to keep a hit (default: 70)")
    ap.add_argument("--evalue", type=float, default=1e-5,
                    help="BLAST e-value cutoff (default: 1e-5)")
    args = ap.parse_args()

    ref_path = Path(args.rdna_ref)
    empty_report = "read_id\tlocus\tinformative_bp\tgate_decision\n"

    if not ref_path.exists():
        print(
            f"[blast] ERROR: rdna_ref not found: {ref_path}\n"
            "  Build it: python scripts/build_rdna_ref.py --email you@email",
            file=sys.stderr,
        )
        Path(args.gate_report).write_text(empty_report)
        Path(args.gated_out).write_text("")
        sys.exit(1)

    with open(args.params) as fh:
        params = yaml.safe_load(fh)
    engine = GateEngine.from_config(params)

    baited = read_fasta(Path(args.baited))
    if not baited:
        Path(args.gate_report).write_text(empty_report)
        Path(args.gated_out).write_text("")
        print("[blast] 0 sequences in baited file", file=sys.stderr)
        return

    with tempfile.TemporaryDirectory() as tmp:
        db_prefix = build_blast_db(ref_path, Path(tmp))
        hits = run_blastn(Path(args.baited), db_prefix, args.min_pident, args.evalue)

    n_fine = n_coarse = n_discard = n_nohit = 0

    with open(args.gate_report, "w") as rep_fh, open(args.gated_out, "w") as out_fh:
        rep_fh.write(empty_report)
        for seq_id, seq in baited.items():
            hit = hits.get(seq_id)
            if hit is None:
                n_nohit += 1
                rep_fh.write(f"{seq_id}\tnone\t0\tdiscard\n")
                continue

            locus = hit["locus"]
            informative_bp = hit["informative_bp"]
            gate_dec = engine.decide(locus, informative_bp)
            rep_fh.write(f"{seq_id}\t{locus}\t{informative_bp}\t{gate_dec.value}\n")

            if gate_dec == GateDecision.FINE:
                n_fine += 1
            elif gate_dec == GateDecision.COARSE:
                n_coarse += 1
            else:
                n_discard += 1
                continue

            out_fh.write(
                f">{seq_id} locus={locus} informative_bp={informative_bp}"
                f" gate={gate_dec.value} pident={hit['pident']:.1f}\n"
                f"{seq}\n"
            )

    total = len(baited)
    print(
        f"[blast] total={total} no_hit={n_nohit} fine={n_fine}"
        f" coarse={n_coarse} discard={n_discard}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
