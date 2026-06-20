#!/usr/bin/env python3
"""
Merge alignment metadata + nt reverse-classification into the hand-checkable
results collection: a master confirmed_hits.tsv and per-plant annotated FASTAs.
"""
from __future__ import annotations
import argparse
from pathlib import Path

_ap = argparse.ArgumentParser()
_ap.add_argument("--res", default="results/alternaria_vs_gbi10")
RES = Path(_ap.parse_args().res)
HITS = RES / "hits"

# Coarse fungal-name keywords (for a hint only; the nt_organism column is the truth).
# Dothideomycetes / Pleosporaceae genera dominate (they share conserved regions with
# the Alternaria genome query). The reverse-BLAST title is what the user hand-checks.
FUNGAL_HINT = ("Alternaria", "Cladosporium", "Sclerophomella", "Zeloasperisporium",
               "Stemphylium", "Bipolaris", "Curvularia", "Cochliobolus", "Exserohilum",
               "Pyrenophora", "Setosphaeria", "Epicoccum", "Ulocladium", "Embellisia",
               "Nimbya", "Drechslera", "Phoma", "Didymella", "Leptosphaeria",
               "Fusarium", "Aspergillus", "Penicillium", "Trichoderma", "Botrytis",
               "Dothideo", "Pleospor", "Ascomyc", "fungal", "fungus", "myco",
               "Sordario", "Eurotio", "Saccharomyces", "Cryptococcus", "Ustilago")


def _organism_from(ssciname: str, title: str) -> str:
    """Remote BLAST often returns ssciname='N/A'; recover genus+species from the title."""
    if ssciname and ssciname != "N/A":
        return ssciname
    t = title
    for pre in ("TPA_asm:", "UPA_asm:", "TPA_inf:", "MAG:", "UNVERIFIED:"):
        if t.startswith(pre):
            t = t[len(pre):]
    toks = t.strip().split()
    return " ".join(toks[:2]) if toks else "NO_HIT"


def main() -> None:
    # alignment metadata
    meta_lines = (HITS / "all_alt_hits.meta.tsv").read_text().splitlines()
    meta_hdr = meta_lines[0].split("\t")
    meta = {r.split("\t")[0]: dict(zip(meta_hdr, r.split("\t"))) for r in meta_lines[1:]}

    # nt blast: qseqid pident length evalue staxids ssciname stitle  (keep best per id)
    nt = {}
    bl = HITS / "all_alt_hits.nt_blast.tsv"
    for line in bl.read_text().splitlines():
        f = line.split("\t")
        if len(f) < 7:
            continue
        qid = f[0]
        if qid in nt:
            continue  # first line per query = best (already -max_target_seqs 1)
        nt[qid] = {"pident": f[1], "length": f[2],
                   "organism": _organism_from(f[5], f[6]), "title": f[6]}

    # load the unitig sequences for the per-plant FASTAs
    seqs, cur = {}, None
    for line in (HITS / "all_alt_hits.fa").read_text().splitlines():
        if line.startswith(">"):
            cur = line[1:].split()[0]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += line.strip()

    out_hdr = ["hit_id", "species", "unitig_len", "our_genome_contig", "our_genome_identity",
               "our_genome_aln_len", "nt_identity", "nt_aln_len", "nt_organism", "call", "nt_title"]
    rows = []
    for hid, m in meta.items():
        b = nt.get(hid, {})
        org = b.get("organism", "NO_HIT")
        title = b.get("title", "")
        is_alt = "Alternaria" in org or "Alternaria" in title
        is_fungal = any(k.lower() in (org + " " + title).lower() for k in FUNGAL_HINT)
        call = "Alternaria" if is_alt else ("other_fungus" if is_fungal else "other/check")
        rows.append([hid, m["species"], m["unitig_len"], m["our_genome_contig"],
                     m["our_genome_identity"], m["our_genome_aln_len"],
                     b.get("pident", "-"), b.get("length", "-"), org, call, title])

    # sort: by plant, then by our identity desc
    rows.sort(key=lambda r: (r[1], -float(r[4])))
    with open(HITS / "confirmed_hits.tsv", "w") as f:
        f.write("\t".join(out_hdr) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    # per-plant annotated FASTAs
    (HITS / "per_plant").mkdir(exist_ok=True)
    by_plant: dict[str, list] = {}
    for r in rows:
        by_plant.setdefault(r[1], []).append(r)
    for sp, rs in by_plant.items():
        with open(HITS / "per_plant" / f"{sp}.alternaria_hits.fa", "w") as f:
            for r in rs:
                hid = r[0]
                f.write(f">{hid} plant={sp} our_contig={r[3]} our_id={r[4]} "
                        f"nt={r[8].replace(' ', '_')} nt_id={r[6]} call={r[9]}\n{seqs.get(hid,'')}\n")

    # console summary
    from collections import Counter
    print(f"{'species':28} {'total':>5} {'Alternaria':>10} {'other_fungus':>12} {'other':>6}")
    for sp, rs in sorted(by_plant.items(), key=lambda x: -len(x[1])):
        c = Counter(r[9] for r in rs)
        print(f"  {sp:26} {len(rs):>5} {c['Alternaria']:>10} {c['other_fungus']:>12} {c['other/check']:>6}")
    print(f"\nwritten: {HITS/'confirmed_hits.tsv'} and {HITS/'per_plant'}/")


if __name__ == "__main__":
    main()
