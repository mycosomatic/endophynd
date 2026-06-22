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
    total_feats = total_reads = 0
    for r in rows:
        if r.get("fungal") != "yes":
            continue
        size = int(r.get("size") or 1)
        g = genus_of(r.get("taxon", ""))
        by_genus_reads[g] += size
        by_genus_feats[g] += 1
        total_feats += 1
        total_reads += size
    return by_genus_reads, by_genus_feats, total_feats, total_reads


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(args.taxonomy) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    reads, feats, tot_f, tot_r = aggregate(rows)

    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["rank", "name", "n_features", "read_support"])
        for g, c in sorted(reads.items(), key=lambda kv: -kv[1]):
            w.writerow(["genus", g, feats[g], c])
        w.writerow(["TOTAL", "fungal", tot_f, tot_r])


if __name__ == "__main__":
    main()
