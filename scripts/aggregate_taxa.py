#!/usr/bin/env python3
"""
Aggregate per-feature ITS taxonomy (from classify_its_blast.py) into a per-accession
fungal taxa table: confident fungal features grouped by genus, weighted by abundance.

Input : taxonomy.tsv with columns feature_id,size,fungal,taxon,pct_identity,aln_len,...
Output: fungal_taxa_table.tsv with columns rank,name,n_features,read_support
        (rank rows for 'genus'; plus a single TOTAL row).
"""
import argparse
import csv
import re
import collections


def genus_of(taxon):
    m = re.search(r"g__([^;]+)", taxon)
    if m and m.group(1):
        return m.group(1)
    # fall back to deepest populated rank
    ranks = [r for r in taxon.split(";") if "__" in r and r.split("__", 1)[1]]
    return ranks[-1].split("__", 1)[1] if ranks else "unresolved"


def aggregate(rows):
    by_genus_reads = collections.Counter()
    by_genus_feats = collections.Counter()
    fung_feats = fung_reads = 0
    all_feats = all_reads = 0
    for r in rows:
        size = int(r.get("size") or 1)
        all_feats += 1
        all_reads += size
        if r.get("fungal") != "yes":
            continue
        g = genus_of(r.get("taxon", ""))
        by_genus_reads[g] += size
        by_genus_feats[g] += 1
        fung_feats += 1
        fung_reads += size
    return {
        "genus_reads": by_genus_reads, "genus_feats": by_genus_feats,
        "fung_feats": fung_feats, "fung_reads": fung_reads,
        "all_feats": all_feats, "all_reads": all_reads,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--min-its", type=int, default=10,
        help="recovery control: min total ITS features (any origin) for recovery_ok=yes. "
             "Gates absence calls — a taxon being absent is only meaningful when the "
             "dataset actually yielded ITS (else the run may simply have failed).",
    )
    args = ap.parse_args(argv)

    with open(args.taxonomy) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    a = aggregate(rows)
    recovery_ok = "yes" if a["all_feats"] >= args.min_its else "no"

    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["rank", "name", "n_features", "read_support"])
        for g, c in sorted(a["genus_reads"].items(), key=lambda kv: -kv[1]):
            w.writerow(["genus", g, a["genus_feats"][g], c])
        w.writerow(["TOTAL", "fungal", a["fung_feats"], a["fung_reads"]])
        # recovery control: total ITS recovered (any origin) is the "did the pipeline
        # work" signal; recovery_ok gates whether an absence call is trustworthy.
        w.writerow(["TOTAL", "all_its", a["all_feats"], a["all_reads"]])
        w.writerow(["recovery", "recovery_ok", recovery_ok, args.min_its])


if __name__ == "__main__":
    main()
