#!/usr/bin/env python3
"""
Leak-frontier stress test: how low can the length threshold go before false
positives leak in? Reads SAMs aligned with a LOW minimap2 floor (e.g. `-s 50`,
so sub-200 bp alignments are reported) and sweeps a dense length × identity grid,
counting hits per reference class (ALT_ real query, NULL_* absent genomes, SHUF_
shuffle). A null/SHUF cell going from 0 → nonzero marks where specificity breaks.

Usage:
  stress_sweep.py --sam-dir results/.../calibration/stress --ref results/.../refs/combined_ref.fa
"""
from __future__ import annotations
import argparse
import glob
from pathlib import Path

from endophynd.target.align import parse_minimap2_sam
from endophynd.target.models import QuerySpec, QueryType
from endophynd.target.query import read_fasta_lengths


def _cls(qid: str) -> str:
    return qid.split("_", 1)[0]


def low_complexity(seq: str, k: int = 3, thresh: float = 0.5) -> bool:
    """True if a sequence is low-complexity (simple repeat / homopolymer / micro-
    satellite). Measured as distinct k-mer fraction: real genomic sequence saturates
    near 1.0; a repeat tract has very few distinct k-mers. This is what leaks at short
    lengths (the leak is repeats, not homology), so dropping these unmasks the floor."""
    seq = seq.upper()
    if len(seq) < 6:
        return True
    kmers = {seq[i:i + k] for i in range(len(seq) - k + 1)}
    denom = min(len(seq) - k + 1, 4 ** k)
    return (len(kmers) / denom) < thresh


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sam-dir", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out")
    ap.add_argument("--mask-lowcomplexity", action="store_true",
                    help="drop hits whose matched sequence is low-complexity (repeat masking)")
    a = ap.parse_args()

    lens = read_fasta_lengths(a.ref)
    qs = QuerySpec(fasta_path="", query_type=QueryType.GENOME, record_lengths=lens)
    hits = []
    for sam in glob.glob(f"{a.sam_dir}/*.sam"):
        with open(sam) as f:
            hits += parse_minimap2_sam(f, qs, min_identity=0.0, min_aln_len=1, min_query_cov=0.0)

    if a.mask_lowcomplexity:
        before = len(hits)
        hits = [h for h in hits if not (h.matched_seq and low_complexity(h.matched_seq))]
        print(f"# low-complexity masking: dropped {before - len(hits)} of {before} hits\n")

    raw = sorted({_cls(k) for k in lens})
    order = ["ALT", "NMOR", "NSAC", "NBOL", "NPSI", "SHUF"]
    classes = [c for c in order if c in raw] + [c for c in raw if c not in order]
    alns = [50, 75, 100, 125, 150, 200]
    ids = [0.99, 0.97, 0.95, 0.90, 0.85, 0.80]

    lines = [f"min aln length reached: {min(h.aln_len for h in hits)} bp  (total mapped {len(hits)})", ""]
    for mid in ids:
        lines.append(f"--- identity >= {mid:.2f} ---")
        lines.append("class\t" + "\t".join(f"L>={x}" for x in alns))
        for c in classes:
            row = [sum(1 for h in hits if _cls(h.query_id) == c and h.identity >= mid and h.aln_len >= x)
                   for x in alns]
            leak = "  <-- LEAK" if c not in ("ALT",) and c != "SHUF" and any(row) else ""
            lines.append(f"{c}\t" + "\t".join(str(n) for n in row) + leak)
        lines.append("")

    txt = "\n".join(lines)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt + "\n")
        print(f"\nwritten: {a.out}")


if __name__ == "__main__":
    main()
