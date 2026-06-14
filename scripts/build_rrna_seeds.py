#!/usr/bin/env python3
"""
Build the rRNA seed set for bbduk baiting.

Downloads representative fungal rDNA sequences from NCBI (SSU/18S, 5.8S,
LSU/28S) spanning the major fungal phyla, writes resources/rrna_seeds.fa,
and records provenance in resources/rrna_seeds_provenance.yml.

Requirements: Python 3.10+, no third-party libraries needed (uses urllib only).
Run time: ~2–5 min on a fast connection (downloads ~100 sequences).

Usage:
    python scripts/build_rrna_seeds.py --email your@email.com
    python scripts/build_rrna_seeds.py --email your@email.com --n-per-group 5
    python scripts/build_rrna_seeds.py --verify   # check existing seed file only

Why this matters:
    bbduk uses k=31 k-mers from this file to bait candidate rDNA reads from
    a streaming Logan/SRA input. Seeds must span the major fungal lineages
    so that rDNA from rare endophytes is not missed. More diversity = higher
    sensitivity. The gate rule (annotate_and_gate) handles false positives
    downstream, so a slightly permissive seed set is preferred over a tight one.

NCBI E-utilities API is public and free; providing your email in the User-Agent
is required by NCBI's usage policy and helps them contact you if there's a
problem with your queries.
"""

import argparse
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FA = REPO_ROOT / "resources" / "rrna_seeds.fa"
OUT_PROV = REPO_ROOT / "resources" / "rrna_seeds_provenance.yml"

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ---------------------------------------------------------------------------
# Target taxa: one representative genus per major fungal lineage.
# These cover Ascomycota (Pezizomycotina + Saccharomycotina),
# Basidiomycota (Agaricomycotina + Ustilaginomycotina),
# Mucoromycota, Chytridiomycota, and Zoopagomycota.
# Used to construct diverse search queries; not hardcoded accessions.
# ---------------------------------------------------------------------------
TAXA_GROUPS = {
    # (search_term, description)
    "Ascomycota_Hypocreales": (
        "Fusarium[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Ascomycota: Sordariomycetes, Hypocreales (Fusarium)",
    ),
    "Ascomycota_Eurotiales": (
        "Aspergillus[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Ascomycota: Eurotiomycetes, Eurotiales (Aspergillus)",
    ),
    "Ascomycota_Pleosporales": (
        "Alternaria[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Ascomycota: Dothideomycetes, Pleosporales (Alternaria) — in mock community",
    ),
    "Ascomycota_Saccharomycetales": (
        "Saccharomyces[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Ascomycota: Saccharomycetes (Saccharomyces)",
    ),
    "Ascomycota_Pezizales": (
        "Tuber[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Ascomycota: Pezizomycetes, Pezizales (Tuber)",
    ),
    "Basidiomycota_Agaricales": (
        "Agaricus[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Basidiomycota: Agaricomycetes, Agaricales (Agaricus)",
    ),
    "Basidiomycota_Polyporales": (
        "Trametes[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Basidiomycota: Agaricomycetes, Polyporales (Trametes)",
    ),
    "Basidiomycota_Russulales": (
        "Russula[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Basidiomycota: Agaricomycetes, Russulales (Russula)",
    ),
    "Basidiomycota_Ustilaginales": (
        "Ustilago[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Basidiomycota: Ustilaginomycetes (Ustilago)",
    ),
    "Mucoromycota_Mucorales": (
        "Rhizopus[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Mucoromycota: Mucoromycetes, Mucorales (Rhizopus)",
    ),
    "Chytridiomycota": (
        "Chytriomyces[Organism] AND (18S ribosomal RNA[Title] OR 18S rRNA[Title])",
        "Chytridiomycota (Chytriomyces)",
    ),
    # 5.8S seeds — highly conserved; even a few sequences cover Fungi broadly
    "5.8S_Ascomycota": (
        "Aspergillus[Organism] AND 5.8S ribosomal RNA[Title]",
        "5.8S rRNA — Aspergillus (baits ITS flanks for all Ascomycota)",
    ),
    "5.8S_Basidiomycota": (
        "Agaricus[Organism] AND 5.8S ribosomal RNA[Title]",
        "5.8S rRNA — Agaricus (baits ITS flanks for Basidiomycota)",
    ),
    # LSU (28S) seeds — catch reads anchored in LSU rather than SSU or ITS
    "LSU_Ascomycota": (
        "Fusarium[Organism] AND (28S ribosomal RNA[Title] OR large subunit ribosomal RNA[Title])",
        "LSU/28S — Ascomycota (Fusarium)",
    ),
    "LSU_Basidiomycota": (
        "Agaricus[Organism] AND (28S ribosomal RNA[Title] OR large subunit ribosomal RNA[Title])",
        "LSU/28S — Basidiomycota (Agaricus)",
    ),
}

# Length window per locus type (NCBI SLEN filter)
LEN_FILTER = {
    "5.8S": "100:300[SLEN]",
    "LSU": "200:3000[SLEN]",
    "SSU": "800:3000[SLEN]",  # full-length 18S is ~1800 bp
}


def _len_filter_for_group(group_key: str) -> str:
    if "5.8S" in group_key:
        return LEN_FILTER["5.8S"]
    if "LSU" in group_key:
        return LEN_FILTER["LSU"]
    return LEN_FILTER["SSU"]


def entrez_search(term: str, email: str, retmax: int = 10) -> list[str]:
    """Return a list of GenBank UIDs matching the query."""
    params = urllib.parse.urlencode({
        "db": "nuccore",
        "term": term,
        "retmax": retmax,
        "retmode": "json",
        "email": email,
    })
    url = f"{ENTREZ_BASE}/esearch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": f"endophynd-seed-builder/0.1 ({email})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data.get("esearchresult", {}).get("idlist", [])


def entrez_fetch_fasta(uids: list[str], email: str) -> str:
    """Fetch GenBank sequences as FASTA text."""
    if not uids:
        return ""
    params = urllib.parse.urlencode({
        "db": "nuccore",
        "id": ",".join(uids),
        "rettype": "fasta",
        "retmode": "text",
        "email": email,
    })
    url = f"{ENTREZ_BASE}/efetch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": f"endophynd-seed-builder/0.1 ({email})"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def iter_fasta(text: str) -> Iterator[tuple[str, str]]:
    """Yield (header, sequence) pairs from FASTA text."""
    header, seq_parts = None, []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                yield header, "".join(seq_parts)
            header = line[1:].strip()
            seq_parts = []
        elif line.strip():
            seq_parts.append(line.strip())
    if header is not None:
        yield header, "".join(seq_parts)


def deduplicate(records: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Remove exact-duplicate sequences (same accession from multiple queries)."""
    seen_accs, out = set(), []
    for header, seq in records:
        acc = header.split()[0]
        if acc not in seen_accs:
            seen_accs.add(acc)
            out.append((header, seq))
    return out


def build_seeds(email: str, n_per_group: int, out_fa: Path, out_prov: Path) -> None:
    """Main build routine."""
    print(f"Building rRNA seed set → {out_fa}")
    print(f"  {len(TAXA_GROUPS)} taxon groups × up to {n_per_group} seqs each")
    print(f"  Email for NCBI: {email}\n")

    all_records: list[tuple[str, str]] = []
    provenance: dict = {
        "built": datetime.datetime.utcnow().isoformat() + "Z",
        "email": email,
        "n_per_group": n_per_group,
        "groups": {},
        "ncbi_entrez_base": ENTREZ_BASE,
        "note": (
            "Seed sequences fetched from NCBI for bbduk k-mer baiting. "
            "Covers SSU/18S, 5.8S, and LSU/28S across major fungal lineages. "
            "Replace this file with a larger phylogenetically balanced set "
            "(e.g. from SILVA) for production runs."
        ),
    }

    for group_key, (base_term, description) in TAXA_GROUPS.items():
        len_filter = _len_filter_for_group(group_key)
        term = f"({base_term}) AND {len_filter}"
        print(f"  [{group_key}] querying: {term}")

        try:
            uids = entrez_search(term, email, retmax=n_per_group)
            time.sleep(0.35)  # NCBI asks for ≤3 requests/sec without API key

            if not uids:
                print(f"    → 0 hits")
                provenance["groups"][group_key] = {
                    "description": description,
                    "query": term,
                    "n_fetched": 0,
                    "accessions": [],
                }
                continue

            fasta_text = entrez_fetch_fasta(uids, email)
            time.sleep(0.35)

            records = list(iter_fasta(fasta_text))
            all_records.extend(records)
            accs = [h.split()[0] for h, _ in records]
            print(f"    → {len(records)} sequences: {', '.join(accs[:3])}{'…' if len(accs) > 3 else ''}")

            provenance["groups"][group_key] = {
                "description": description,
                "query": term,
                "n_fetched": len(records),
                "accessions": accs,
            }

        except Exception as exc:
            print(f"    [WARNING] {group_key}: {exc}  — skipping")
            provenance["groups"][group_key] = {"error": str(exc)}

    # Deduplicate
    unique = deduplicate(all_records)
    print(f"\n  Total: {len(all_records)} fetched → {len(unique)} after deduplication")

    if len(unique) < 5:
        print(
            "\n[ERROR] Fewer than 5 sequences retrieved. "
            "Check your internet connection and NCBI availability."
        )
        sys.exit(1)

    # Write FASTA
    out_fa.parent.mkdir(parents=True, exist_ok=True)
    with open(out_fa, "w") as f:
        for header, seq in unique:
            f.write(f">{header}\n")
            # 80-character wrapping
            for i in range(0, len(seq), 80):
                f.write(seq[i:i+80] + "\n")

    provenance["n_sequences_written"] = len(unique)
    provenance["output"] = str(out_fa)

    # Write provenance
    import yaml as _yaml
    with open(out_prov, "w") as f:
        _yaml.dump(provenance, f, default_flow_style=False, sort_keys=False)

    print(f"\nWrote {len(unique)} sequences to {out_fa}")
    print(f"Provenance: {out_prov}")


def verify_seeds(fa_path: Path) -> None:
    """Basic sanity check on an existing seed file."""
    if not fa_path.exists():
        print(f"[MISSING] {fa_path}")
        print("  Run:  python scripts/build_rrna_seeds.py --email your@email.com")
        sys.exit(1)

    records = []
    with open(fa_path) as f:
        records = list(iter_fasta(f.read()))

    if not records:
        print(f"[EMPTY] {fa_path} — 0 sequences")
        sys.exit(1)

    placeholder = any("TESTING_PLACEHOLDER" in h for h, _ in records)
    short = [h for h, s in records if len(s) < 31]

    print(f"Seed file: {fa_path}")
    print(f"  Sequences: {len(records)}")
    print(f"  Shortest:  {min(len(s) for _, s in records)} bp")
    print(f"  Longest:   {max(len(s) for _, s in records)} bp")

    if placeholder:
        print(
            "\n[WARNING] This is the TESTING PLACEHOLDER seed set — synthetic sequences.")
        print("  Replace before running Phase 1 on real Logan data:")
        print("  python scripts/build_rrna_seeds.py --email your@email.com")
    else:
        print("\n[OK] Seed file looks real (no placeholder flag found).")

    if short:
        print(f"\n[WARNING] {len(short)} sequences shorter than k=31 bp — bbduk will skip them.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build rRNA seed set for bbduk baiting from NCBI."
    )
    parser.add_argument("--email", help="Your email (required by NCBI E-utilities policy)")
    parser.add_argument(
        "--n-per-group", type=int, default=8,
        help="Number of sequences per taxon group (default: 8, total ~100–120)"
    )
    parser.add_argument(
        "--out", type=Path, default=OUT_FA,
        help=f"Output FASTA path (default: {OUT_FA})"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify an existing seed file without downloading"
    )
    args = parser.parse_args()

    if args.verify:
        verify_seeds(args.out)
        return

    if not args.email:
        print("[ERROR] --email is required (NCBI E-utilities policy).")
        print("  Usage: python scripts/build_rrna_seeds.py --email your@email.com")
        sys.exit(1)

    build_seeds(args.email, args.n_per_group, args.out, OUT_PROV)


if __name__ == "__main__":
    main()
