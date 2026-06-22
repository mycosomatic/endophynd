#!/usr/bin/env python3
"""
Fetch a broad pan-fungal conserved single-copy marker panel (RPB2, TEF1-a,
beta-tubulin) spanning the major fungal lineages, for use as a "are there ANY
fungi here?" probe via the inverted/targeted strategy.

Markers are non-ribosomal and single-copy on purpose: rDNA collapses in Logan
(D20), and single-copy markers assemble cleanly. The panel is deliberately
diverse so that any fungus in a dataset matches its nearest panel member; a high
identity threshold at search time then keeps the plant host's own ortholog out.

Sequences are fetched (not fabricated) from NCBI nuccore; each output header
records the source accession and original defline for provenance.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# NCBI etiquette: identify yourself. Set via --email or NCBI_EMAIL/ENTREZ_EMAIL env;
# main() resolves it (no hard-coded address).
EMAIL = os.environ.get("NCBI_EMAIL") or os.environ.get("ENTREZ_EMAIL") or ""

# (label_marker, genus, lineage, extra title terms, slen range)
PANEL = [
    ("RPB2", "Aspergillus",   "Eurotiomycetes",   "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Fusarium",      "Sordariomycetes",  "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Cladosporium",  "Dothideomycetes",  "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Botrytis",      "Leotiomycetes",    "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Saccharomyces", "Saccharomycotina", "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Cryptococcus",  "Tremellomycetes",  "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Ustilago",      "Ustilaginomycetes","RPB2[Title]",                       "700:4000"),
    ("RPB2", "Agaricus",      "Agaricomycetes",   "RPB2[Title]",                       "700:4000"),
    ("RPB2", "Rhizopus",      "Mucoromycota",     "RPB2[Title]",                       "700:4000"),
    ("TEF1", "Trichoderma",   "Sordariomycetes",  '(tef1[Title] OR "elongation factor 1-alpha"[Title])', "400:3000"),
    ("TEF1", "Penicillium",   "Eurotiomycetes",   '(tef1[Title] OR "elongation factor 1-alpha"[Title])', "400:3000"),
    ("TEF1", "Mortierella",   "Mucoromycota",     '(tef1[Title] OR "elongation factor 1-alpha"[Title])', "400:3000"),
    ("TUB2", "Cladosporium",  "Dothideomycetes",  '(beta-tubulin[Title] OR "beta tubulin"[Title] OR benA[Title])', "400:3000"),
    ("TUB2", "Penicillium",   "Eurotiomycetes",   '(beta-tubulin[Title] OR "beta tubulin"[Title] OR benA[Title])', "400:3000"),
]


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": f"endophynd ({EMAIL})"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def esearch_first(term: str) -> str | None:
    q = urllib.parse.urlencode(
        {"db": "nuccore", "term": term, "retmax": "1", "sort": "relevance",
         "retmode": "json", "email": EMAIL, "tool": "endophynd"}
    )
    import json
    ids = json.loads(_get(f"{EUTILS}/esearch.fcgi?{q}"))["esearchresult"]["idlist"]
    return ids[0] if ids else None


def efetch_fasta(uid: str) -> str:
    q = urllib.parse.urlencode(
        {"db": "nuccore", "id": uid, "rettype": "fasta", "retmode": "text",
         "email": EMAIL, "tool": "endophynd"}
    )
    return _get(f"{EUTILS}/efetch.fcgi?{q}")


def main() -> None:
    global EMAIL
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", default="resources/fungal_markers.fa",
                    help="output FASTA (default: resources/fungal_markers.fa)")
    ap.add_argument("--email", default=EMAIL,
                    help="contact email for NCBI EUtils (or set NCBI_EMAIL/ENTREZ_EMAIL)")
    args = ap.parse_args()
    if not args.email:
        ap.error("NCBI requires a contact email: pass --email or set NCBI_EMAIL")
    EMAIL = args.email
    out = args.out
    records = []
    for marker, genus, lineage, extra, slen in PANEL:
        term = f"{genus}[Organism] AND {extra} AND {slen}[SLEN]"
        try:
            uid = esearch_first(term)
            if not uid:
                print(f"  [skip] {marker} {genus}: no hit", file=sys.stderr); continue
            fa = efetch_fasta(uid).strip()
            header, *seqlines = fa.splitlines()
            acc = header[1:].split()[0]
            defline = header[1:].strip()
            seq = "".join(seqlines)
            new = f">FUNGAL_{marker}_{genus} acc={acc} lineage={lineage} | {defline}"
            records.append((new, seq))
            print(f"  [ok] {marker:5} {genus:14} {lineage:18} {acc:14} {len(seq)} bp", file=sys.stderr)
        except Exception as e:
            print(f"  [err] {marker} {genus}: {e}", file=sys.stderr)
        time.sleep(0.34)  # be polite to NCBI (no API key → 3 req/s)

    with open(out, "w") as f:
        for h, s in records:
            f.write(h + "\n")
            for i in range(0, len(s), 80):
                f.write(s[i:i + 80] + "\n")
    print(f"\nwrote {len(records)} marker sequences → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
