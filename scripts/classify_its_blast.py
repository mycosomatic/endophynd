#!/usr/bin/env python3
"""
Classify recovered ITS features against UNITE by blastn identity.

This is the VALIDATED discovery-mode classifier (D30). The fungal/non-fungal call
is made by BLAST identity to the UNITE (Fungi-only) reference over ITSx-extracted
ITS1/ITS2 — NOT by sintax/naive-Bayes `k:Fungi`, which labels every query Fungi
against a Fungi-only database and so cannot separate host-plant ITS from fungal ITS.
Because ITSx has already stripped the conserved 5.8S, a plant ITS cannot reach the
identity/coverage bar against a fungal reference.

A feature is called fungal iff blastn returns a hit at >= min_identity over
>= min_qcov of the query. Features with no passing hit are 'unclassified'
(host plant, other eukaryote, or non-ITS).

Usage (pipeline):
  classify_its_blast.py --features f.fa --db unite_blast --out taxonomy.tsv \
      --min-identity 90 --min-qcov 60 --threads 4
Testing / re-analysis:
  classify_its_blast.py --features f.fa --blast-tsv precomputed.tsv --out taxonomy.tsv
"""
import argparse
import re
import subprocess
import sys

OUTFMT = "6 qseqid sseqid pident length qcovhsp"
COLUMNS = ["feature_id", "size", "fungal", "taxon", "pct_identity", "aln_len", "unite_subject"]


def parse_unite_lineage(sseqid):
    """UNITE header 'Name|ACC|SH|type|k__Fungi;p__...;s__...' -> lineage string."""
    parts = sseqid.split("|")
    return parts[4] if len(parts) >= 5 else ""


def read_features(features_fa):
    """Return ordered list of (feature_id, size) from a FASTA with ;size=N headers."""
    out = []
    with open(features_fa) as fh:
        for line in fh:
            if line.startswith(">"):
                fid = line[1:].split()[0].strip()
                m = re.search(r"size=(\d+)", fid)
                size = int(m.group(1)) if m else 1
                out.append((fid, size))
    return out


def best_hits(blast_rows):
    """Collapse blastn rows to one best hit per query (max identity, then length)."""
    best = {}
    for r in blast_rows:
        if len(r) < 5:
            continue
        q, s = r[0], r[1]
        pid, ln, qcov = float(r[2]), int(r[3]), float(r[4])
        key = (pid, ln)
        if q not in best or key > (best[q][0], best[q][1]):
            best[q] = (pid, ln, qcov, s)
    return best


def classify(features, blast_rows):
    """Pure: (features=[(id,size)], blast_rows) -> list of dict records (COLUMNS)."""
    best = best_hits(blast_rows)
    records = []
    for fid, size in features:
        if fid in best:
            pid, ln, qcov, s = best[fid]
            records.append({
                "feature_id": fid, "size": size, "fungal": "yes",
                "taxon": parse_unite_lineage(s) or "k__Fungi",
                "pct_identity": f"{pid:.3f}", "aln_len": ln, "unite_subject": s,
            })
        else:
            records.append({
                "feature_id": fid, "size": size, "fungal": "no",
                "taxon": "unclassified", "pct_identity": "", "aln_len": "", "unite_subject": "",
            })
    return records


def run_blastn(features_fa, db, min_identity, min_qcov, threads):
    cmd = [
        "blastn", "-query", features_fa, "-db", db,
        "-perc_identity", str(min_identity), "-qcov_hsp_perc", str(min_qcov),
        "-max_target_seqs", "1", "-outfmt", OUTFMT, "-num_threads", str(threads),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"blastn failed (rc={proc.returncode})")
    return [line.split("\t") for line in proc.stdout.splitlines() if line.strip()]


def write_tsv(records, out_path):
    with open(out_path, "w") as fh:
        fh.write("\t".join(COLUMNS) + "\n")
        for r in records:
            fh.write("\t".join(str(r[c]) for c in COLUMNS) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True, help="dereplicated ITS FASTA (;size=N headers)")
    ap.add_argument("--db", help="UNITE blastn DB prefix (required unless --blast-tsv)")
    ap.add_argument("--out", required=True, help="output taxonomy TSV")
    ap.add_argument("--blast-tsv", help="precomputed blastn outfmt-6 tsv (skips running blastn)")
    ap.add_argument("--min-identity", type=float, default=90.0)
    ap.add_argument("--min-qcov", type=float, default=60.0)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args(argv)

    features = read_features(args.features)
    if args.blast_tsv:
        with open(args.blast_tsv) as fh:
            blast_rows = [line.split("\t") for line in fh if line.strip()]
    else:
        if not args.db:
            ap.error("--db is required unless --blast-tsv is given")
        blast_rows = run_blastn(args.features, args.db, args.min_identity, args.min_qcov, args.threads)

    records = classify(features, blast_rows)
    write_tsv(records, args.out)
    n_fungal = sum(1 for r in records if r["fungal"] == "yes")
    sys.stderr.write(f"[classify] {len(features)} features; {n_fungal} confident fungal ITS\n")


if __name__ == "__main__":
    main()
