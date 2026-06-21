#!/usr/bin/env python3
"""
False-positive-rate calibration from the multi-null scan.

The combined reference carries the real query (ALT_) plus biologically-absent
genome nulls at increasing phylogenetic distance and a composition-matched shuffle:

  ALT_   Alternaria NS26-3-C2          — the real query
  NMOR_  Morchella conica              — Ascomycota / Pezizomycetes (nearer asco)
  NSAC_  Saccharomyces cerevisiae      — Ascomycota / Saccharomycotina
  NBOL_  Boletus edulis                — Basidiomycota / Boletales (far)
  NPSI_  Psilocybe zapotecorum         — Basidiomycota / Agaricales (far, neotropical)
  SHUF_  shuffled Alternaria           — zero homology → pure-chance floor

Every hit to a null is, by construction, a false positive. So per (identity,
length) threshold, the null hit counts ARE the false-positive floor, and a
threshold is calibrated when the ALT signal sits clearly above it. The shuffle
floor should be ~0 (random sequence shouldn't align); the real-genome nulls
measure the conserved-region (rRNA/mito/ultraconserved) cross-match floor, which
should roughly match the mito/rRNA cross-matches we strip from ALT by hand.

Outputs (under <res>/calibration/): fpr_sweep.tsv, operating_point.tsv, and the
null hit sequences for optional reverse-classification.
"""
from __future__ import annotations
import argparse
import os
from collections import defaultdict
from pathlib import Path

from endophynd.target.align import parse_minimap2_sam
from endophynd.target.models import QuerySpec, QueryType
from endophynd.target.query import read_fasta_lengths


def _cls(qid: str) -> str:
    return qid.split("_", 1)[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="results/alternaria_vs_gbi10")
    ap.add_argument("--floor-id", type=float, default=0.80)
    ap.add_argument("--floor-aln", type=int, default=150)
    ap.add_argument("--op-id", type=float, default=0.95)
    ap.add_argument("--op-aln", type=int, default=200)
    a = ap.parse_args()
    res = Path(a.res)
    outdir = res / "calibration"
    outdir.mkdir(parents=True, exist_ok=True)

    lens = read_fasta_lengths(res / "refs" / "combined_ref.fa")
    qs = QuerySpec(fasta_path="", query_type=QueryType.GENOME, record_lengths=lens)
    plants = [l.split("\t") for l in (res / "plants10.tsv").read_text().splitlines() if l.strip()]
    # class order: ALT first, then nulls, SHUF last
    raw = sorted({_cls(k) for k in lens})
    order = ["ALT", "NMOR", "NSAC", "NBOL", "NPSI", "SHUF"]
    classes = [c for c in order if c in raw] + [c for c in raw if c not in order]

    per_plant_hits: dict[str, list] = {}
    for run, sp, fam in plants:
        sam = res / "per_plant" / f"{run}.sam"
        if not sam.exists():
            per_plant_hits[sp] = []
            continue
        with open(sam) as f:
            per_plant_hits[sp] = parse_minimap2_sam(
                f, qs, min_identity=a.floor_id, min_aln_len=a.floor_aln, min_query_cov=0.0
            )

    # ---- threshold sweep (totals across datasets) ----
    id_grid = [0.90, 0.93, 0.95, 0.97, 0.99]
    aln_grid = [200, 300, 500]
    sweep = outdir / "fpr_sweep.tsv"
    with open(sweep, "w") as f:
        f.write("min_identity\tmin_aln_len\t" + "\t".join(classes) + "\tnull_floor\tALT_over_floor\n")
        print("=== FPR sweep — total hits across all datasets, by class ===")
        print(f"{'id':>5} {'aln':>4}  " + "  ".join(f"{c:>5}" for c in classes) + "   floor  ALT/floor")
        for mid in id_grid:
            for maln in aln_grid:
                counts = {c: 0 for c in classes}
                for hits in per_plant_hits.values():
                    for h in hits:
                        if h.identity >= mid and h.aln_len >= maln:
                            counts[_cls(h.query_id)] += 1
                nulls = [counts[c] for c in classes if c != "ALT"]
                floor = max(nulls) if nulls else 0
                alt = counts.get("ALT", 0)
                ratio = f"{alt/floor:.1f}x" if floor else ("inf" if alt else "-")
                f.write(f"{mid}\t{maln}\t" + "\t".join(str(counts[c]) for c in classes)
                        + f"\t{floor}\t{ratio}\n")
                print(f"{mid:>5.2f} {maln:>4}  " + "  ".join(f"{counts[c]:>5}" for c in classes)
                      + f"   {floor:>5}  {ratio:>7}")

    # ---- operating point: per-plant, per-class ----
    op = outdir / "operating_point.tsv"
    with open(op, "w") as f:
        f.write(f"# operating point: identity>={a.op_id}, aln_len>={a.op_aln}\n")
        f.write("dataset\t" + "\t".join(classes) + "\n")
        for run, sp, fam in plants:
            counts = {c: 0 for c in classes}
            for h in per_plant_hits.get(sp, []):
                if h.identity >= a.op_id and h.aln_len >= a.op_aln:
                    counts[_cls(h.query_id)] += 1
            f.write(sp + "\t" + "\t".join(str(counts[c]) for c in classes) + "\n")

    # ---- write null hit sequences (for reverse-classification of the FP floor) ----
    nf = outdir / "null_hits.fa"
    nn = 0
    with open(nf, "w") as f:
        for sp, hits in per_plant_hits.items():
            for h in hits:
                c = _cls(h.query_id)
                if c not in ("ALT",) and c != "SHUF" and h.identity >= a.op_id and h.aln_len >= a.op_aln and h.matched_seq:
                    f.write(f">{sp}__{h.matched_seq_id} class={c} query={h.query_id} "
                            f"id={h.identity:.3f} aln={h.aln_len}\n{h.matched_seq}\n")
                    nn += 1

    print(f"\nwrote {sweep}, {op}, and {nf} ({nn} real-genome-null hit seqs @ op point)")
    print("Interpretation: SHUF should be ~0 (no pure-chance hits); the real-genome")
    print("null floor estimates the conserved-region cross-match FP rate — compare it")
    print("to the ALT mito/rRNA cross-matches stripped in the pilot (~23).")


if __name__ == "__main__":
    main()
