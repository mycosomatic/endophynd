#!/usr/bin/env python3
"""
Collect every corrected ALT-class hit from the GBI scan SAMs into a master FASTA
(for reverse-classification) and a metadata TSV.

Corrected thresholds (see D23): low-abundance endophyte DNA assembles into short
Logan unitigs, so we keep hits >= --min-id identity over >= --min-aln bp (default
0.95 / 200), then confirm each by BLAST vs nt downstream.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from endophynd.target.align import parse_minimap2_sam
from endophynd.target.models import QuerySpec, QueryType
from endophynd.target.query import read_fasta_lengths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="results/alternaria_vs_gbi10")
    ap.add_argument("--min-id", type=float, default=0.95)
    ap.add_argument("--min-aln", type=int, default=200)
    a = ap.parse_args()

    res = Path(a.res)
    lens = read_fasta_lengths(res / "refs" / "combined_ref.fa")
    qs = QuerySpec(fasta_path="", query_type=QueryType.GENOME, record_lengths=lens)
    plants = [l.split("\t") for l in (res / "plants10.tsv").read_text().splitlines() if l.strip()]

    fasta = res / "hits" / "all_alt_hits.fa"
    meta = res / "hits" / "all_alt_hits.meta.tsv"
    fasta.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(fasta, "w") as fa:
        for run, sp, fam in plants:
            sam = res / "per_plant" / f"{run}.sam"
            if not sam.exists():
                continue
            with open(sam) as f:
                hits = parse_minimap2_sam(f, qs, min_identity=a.min_id, min_aln_len=a.min_aln, min_query_cov=0.0)
            alt = [h for h in hits if h.query_id.startswith("ALT_")]
            for h in alt:
                hid = f"{sp}__{h.matched_seq_id}"
                contig = h.query_id.replace("ALT_", "").split("_length_")[0]
                fa.write(f">{hid} our_contig={contig} our_id={h.identity:.4f} "
                         f"our_aln={h.aln_len} our_pos={h.query_start}-{h.query_end}\n{h.matched_seq}\n")
                rows.append([hid, run, sp, fam, str(len(h.matched_seq)), contig,
                             f"{h.identity:.4f}", str(h.aln_len),
                             f"{h.query_start}", f"{h.query_end}", h.strand])

    with open(meta, "w") as m:
        m.write("hit_id\trun\tspecies\tfamily\tunitig_len\tour_genome_contig\t"
                "our_genome_identity\tour_genome_aln_len\tour_pos_start\tour_pos_end\tstrand\n")
        for r in rows:
            m.write("\t".join(r) + "\n")

    print(f"extracted {len(rows)} ALT hits → {fasta}")
    print(f"metadata → {meta}")
    # per-plant counts
    from collections import Counter
    c = Counter(r[2] for r in rows)
    for sp, n in sorted(c.items(), key=lambda x: -x[1]):
        print(f"  {sp:28} {n}")


if __name__ == "__main__":
    main()
