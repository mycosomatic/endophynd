#!/usr/bin/env python3
"""Assemble the per-plant 3-class confidence scan into one summary TSV + a call."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

RES = Path("results/alternaria_vs_gbi10")
PP = RES / "per_plant"
plants = [l.split("\t") for l in (RES / "plants10.tsv").read_text().splitlines() if l.strip()]
_HASH_RE = re.compile(r"of (\d+) distinct query hashes, (\d+) were found")


def containment(run: str, tag: str):
    f = PP / f"{run}.{tag}.containment.txt"
    if not f.exists():
        return (0, 0)
    m = _HASH_RE.search(f.read_text())
    return (int(m.group(2)), int(m.group(1))) if m else (0, 0)


def call(alt_strict, alt_cf, fungal_n) -> str:
    alt_present = alt_strict >= 50 or alt_cf >= 0.03
    fungi = fungal_n >= 1 or alt_present
    if alt_present:
        return "Alternaria PRESENT"
    if fungi:
        return "Alternaria absent; other fungi present"
    return "no fungal signal (INCONCLUSIVE)"


hdr = ["run", "species", "family", "ALT_strict_hits", "ALT_breadth", "ALT_med_id",
       "ALT_max_aln", "ALT_contain_frac", "ALT_approx_kb", "CTRL_strict_hits",
       "CTRL_contain_frac", "FUNGAL_n", "FUNGAL_members", "CALL"]
rows = []
for run, sp, fam in plants:
    pj = PP / f"{run}.profile.json"
    if not pj.exists():
        rows.append([run, sp, fam] + ["NA"] * (len(hdr) - 3)); continue
    cls = json.loads(pj.read_text())["classes"]
    a, c, fu = cls["ALT"], cls["CTRL"], cls["FUNGAL"]
    af, at = containment(run, "alt")
    cf, ct = containment(run, "ctrl")
    acf = af / at if at else 0.0
    fmem = ",".join(m.replace("FUNGAL_", "") for m in fu.get("markers_hit", [])) or "-"
    rows.append([
        run, sp, fam, a["n_id95_aln500"], f"{a['breadth_strict_frac']:.5f}",
        f"{a['median_identity']:.3f}", a["max_aln_len"], f"{acf:.5f}", af,
        c["n_id95_aln500"], f"{(cf/ct if ct else 0):.5f}",
        fu.get("n_markers_hit", 0), fmem,
        call(a["n_id95_aln500"], acf, fu.get("n_markers_hit", 0)),
    ])

out = RES / "SUMMARY.tsv"
with open(out, "w") as fh:
    fh.write("\t".join(hdr) + "\n")
    for r in rows:
        fh.write("\t".join(str(x) for x in r) + "\n")
print("\t".join(hdr))
for r in rows:
    print("\t".join(str(x) for x in r))
print(f"\nwritten: {out}", file=sys.stderr)
