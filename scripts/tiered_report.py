#!/usr/bin/env python3
"""
Two-tier reporting for a targeted scan + a seeded random QC subset.

The tiers are filters on ONE alignment (run scan_one_plant.sh with a low minimap2
floor — the default `-s 50` — so sub-200 bp alignments are reported). Default tiers:

  >=200 bp  high-confidence   (calibrated false-positive floor 0; D29)
  >=125 bp  sensitive         (floor 0, ~25x more signal; rDNA leak already excluded)

For each dataset it reports the query (ALT_) hit count at each tier and, if the
combined reference carries null classes (NMOR_/NBOL_/NPSI_/NSAC_/SHUF_, D29), the
false-positive floor at each tier. It does NOT classify every hit (targeted mode is
self-classifying — a hit already matched the query). Instead it draws a SEEDED random
subset of sensitive-tier hits to `qc_sample.fa` for a reverse-classification QC spot
check (e.g. `blastn -query qc_sample.fa -db nt -remote`).
"""
from __future__ import annotations
import argparse
import random
from pathlib import Path

from endophynd.target.align import parse_minimap2_sam
from endophynd.target.models import QuerySpec, QueryType
from endophynd.target.query import read_fasta_lengths

# Valid (reliably-absent) null classes for the false-positive floor. NSAC/CTRL
# (S. cerevisiae) are deliberately EXCLUDED: yeasts are common endophytes/contaminants,
# so yeast is a plausible real presence, not a valid null (D29).
NULL_PREFIXES = {"NMOR", "NBOL", "NPSI", "SHUF"}


def _cls(qid: str) -> str:
    return qid.split("_", 1)[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="results/alternaria_vs_gbi10")
    ap.add_argument("--sam-dir", help="default <res>/per_plant")
    ap.add_argument("--out", help="default <res>/tiered")
    ap.add_argument("--tiers", default="200,125", help="length tiers, high->low")
    ap.add_argument("--min-id", type=float, default=0.95)
    ap.add_argument("--query-class", default="ALT")
    ap.add_argument("--qc-sample", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    res = Path(a.res)
    sam_dir = Path(a.sam_dir) if a.sam_dir else res / "per_plant"
    out = Path(a.out) if a.out else res / "tiered"
    out.mkdir(parents=True, exist_ok=True)
    tiers = sorted((int(t) for t in a.tiers.split(",")), reverse=True)

    lens = read_fasta_lengths(res / "refs" / "combined_ref.fa")
    qs = QuerySpec(fasta_path="", query_type=QueryType.GENOME, record_lengths=lens)
    plants = [l.split("\t") for l in (res / "plants10.tsv").read_text().splitlines() if l.strip()]
    nulls = [c for c in {_cls(k) for k in lens} if c != a.query_class and c in NULL_PREFIXES]
    floor = min(tiers)

    hdr = (["dataset"] + [f"hits>={t}" for t in tiers]
           + ([f"floor>={t}" for t in tiers] if nulls else []))
    rows, pool = [], []
    for run, sp, fam in plants:
        sam = sam_dir / f"{run}.sam"
        hits = []
        if sam.exists():
            with open(sam) as f:
                hits = parse_minimap2_sam(f, qs, min_identity=a.min_id, min_aln_len=floor, min_query_cov=0.0)
        q = {t: sum(1 for h in hits if _cls(h.query_id) == a.query_class and h.aln_len >= t) for t in tiers}
        fl = {t: max([sum(1 for h in hits if _cls(h.query_id) == c and h.aln_len >= t) for c in nulls], default=0)
              for t in tiers}
        row = [sp] + [str(q[t]) for t in tiers] + ([str(fl[t]) for t in tiers] if nulls else [])
        rows.append(row)
        for h in hits:
            if _cls(h.query_id) == a.query_class and h.matched_seq and h.aln_len >= floor:
                pool.append((sp, h))

    comp = out / "tiered_summary.tsv"
    comp.write_text("\t".join(hdr) + "\n" + "\n".join("\t".join(r) for r in rows) + "\n")

    rng = random.Random(a.seed)
    sample = rng.sample(pool, min(a.qc_sample, len(pool)))
    qc = out / "qc_sample.fa"
    with open(qc, "w") as f:
        for sp, h in sample:
            f.write(f">{sp}__{h.matched_seq_id} id={h.identity:.3f} aln={h.aln_len}\n{h.matched_seq}\n")

    print("\t".join(hdr))
    for r in rows:
        print("\t".join(r))
    print(f"\nQC: {len(sample)} of {len(pool)} sensitive-tier (>={floor}bp) hits sampled "
          f"(seed {a.seed}) -> {qc}")
    print(f"comparison -> {comp}")
    if not nulls:
        print("(no null classes in the reference -> false-positive floor not reported; "
              "use the calibration reference to include it)")


if __name__ == "__main__":
    main()
