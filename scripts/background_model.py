#!/usr/bin/env python3
"""
Cross-sample background / contamination model for discovery (review #4, D30 limit).

The same fungal genera recurring across many *unrelated* samples are likely a shared
background — reagent/kit, environmental, or Illumina index-hopping — not host-specific
biology. Without negative controls we use a PREVALENCE heuristic (the idea behind the
decontam package's prevalence method): a genus present in >= prevalence_fraction of the
RECOVERED samples is flagged 'background'. The biologically meaningful signal is what
remains — the distinctive taxa, especially rarer ones (cf. D28: value is greatest for
rarer, less contaminant-prone taxa).

Consumes per-accession fungal_taxa_table.tsv files (build_feature_table output),
honors recovery_ok (a sample that did not recover ITS is excluded from the prevalence
denominator and from absence reasoning — see review #1), and writes:
  - taxa_matrix.tsv      genus x sample read-support matrix
  - genus_background.tsv per-genus prevalence, total reads, background flag
  - distinctive_taxa.tsv per (recovered) sample, the non-background genera = the signal

Usage:
  background_model.py --results-dir <run_results_dir> --out-dir <dir> [--prevalence 0.5] [--min-reads 1]
  background_model.py --tables a/fungal_taxa_table.tsv b/... --out-dir <dir>
"""
import argparse
import csv
import glob
import os


def load_table(path):
    """Return (sample_id, recovery_ok: bool, {genus: read_support})."""
    sample_id = os.path.basename(os.path.dirname(os.path.abspath(path))) or path
    genera = {}
    recovery_ok = True  # default True if the table predates the recovery flag
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            rank = (row.get("rank") or "").strip()
            name = (row.get("name") or "").strip()
            if rank == "genus":
                genera[name] = int(row.get("read_support") or 0)
            elif rank == "recovery" and name == "recovery_ok":
                recovery_ok = (row.get("n_features") or "").strip().lower() == "yes"
    return sample_id, recovery_ok, genera


def build_model(samples, prevalence_fraction=0.5, min_reads=1):
    """samples = [(sample_id, recovery_ok, {genus: reads})].
    Returns dict with matrix, genus_stats, distinctive, and the sample partition."""
    recovered = [s for s in samples if s[1]]
    excluded = [s[0] for s in samples if not s[1]]
    n_rec = len(recovered)
    all_genera = sorted({g for _, _, gd in recovered for g, r in gd.items() if r >= min_reads})

    genus_stats = {}
    for g in all_genera:
        present = [sid for sid, _, gd in recovered if gd.get(g, 0) >= min_reads]
        total = sum(gd.get(g, 0) for _, _, gd in recovered)
        prev = (len(present) / n_rec) if n_rec else 0.0
        genus_stats[g] = {
            "n_present": len(present), "prevalence": prev, "total_reads": total,
            "background": "yes" if (n_rec and prev >= prevalence_fraction) else "no",
        }

    distinctive = {}  # sample_id -> [(genus, reads)] of non-background genera
    for sid, _, gd in recovered:
        rows = [(g, gd[g]) for g in gd
                if gd[g] >= min_reads and genus_stats.get(g, {}).get("background") == "no"]
        distinctive[sid] = sorted(rows, key=lambda x: -x[1])

    return {
        "recovered": [s[0] for s in recovered], "excluded": excluded,
        "genera": all_genera, "genus_stats": genus_stats, "distinctive": distinctive,
        "matrix": {sid: gd for sid, _, gd in recovered},
    }


def write_outputs(model, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    samples = model["recovered"]
    genera = model["genera"]

    with open(os.path.join(out_dir, "taxa_matrix.tsv"), "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["genus"] + samples)
        for g in genera:
            w.writerow([g] + [model["matrix"][s].get(g, 0) for s in samples])

    with open(os.path.join(out_dir, "genus_background.tsv"), "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["genus", "n_samples_present", "n_recovered_samples",
                    "prevalence", "total_read_support", "background"])
        for g in sorted(genera, key=lambda x: (-model["genus_stats"][x]["prevalence"],
                                               -model["genus_stats"][x]["total_reads"])):
            s = model["genus_stats"][g]
            w.writerow([g, s["n_present"], len(samples), f"{s['prevalence']:.3f}",
                        s["total_reads"], s["background"]])

    with open(os.path.join(out_dir, "distinctive_taxa.tsv"), "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample", "genus", "read_support"])
        for sid in samples:
            for g, r in model["distinctive"][sid]:
                w.writerow([sid, g, r])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", help="run results dir; scans */fungal_taxa_table.tsv")
    ap.add_argument("--tables", nargs="*", default=[], help="explicit fungal_taxa_table.tsv paths")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--prevalence", type=float, default=0.5,
                    help="genus in >= this fraction of recovered samples -> background")
    ap.add_argument("--min-reads", type=int, default=1)
    args = ap.parse_args(argv)

    paths = list(args.tables)
    if args.results_dir:
        paths += sorted(glob.glob(os.path.join(args.results_dir, "*", "fungal_taxa_table.tsv")))
    if not paths:
        ap.error("no taxa tables found (use --results-dir or --tables)")

    samples = [load_table(p) for p in paths]
    model = build_model(samples, prevalence_fraction=args.prevalence, min_reads=args.min_reads)
    write_outputs(model, args.out_dir)

    n_bg = sum(1 for g in model["genera"] if model["genus_stats"][g]["background"] == "yes")
    print(f"[background] {len(model['recovered'])} recovered samples"
          f" ({len(model['excluded'])} excluded: {model['excluded']}); "
          f"{len(model['genera'])} genera, {n_bg} flagged background "
          f"(prevalence >= {args.prevalence}). Outputs in {args.out_dir}/")


if __name__ == "__main__":
    main()
