#!/usr/bin/env python3
"""
Build the per-locus rDNA BLAST reference for locus assignment.

Produces resources/rdna_ref.fa where every sequence ID starts with a locus
prefix (SSU_, ITS_, LSU_).  assign_locus_blast.py uses this to assign each
baited unitig to its rDNA region.

Why this is needed:
  ITSx requires conserved SSU/LSU flanking regions to call ITS boundaries.
  Logan unitigs (~200 bp average) are too short to span those flanks, so
  ITSx detects nothing.  BLAST against locus-labeled references assigns a
  region even from a 150 bp fragment with no flanking sequence.

Sources:
  SSU / LSU  — extracted from resources/rrna_seeds.fa (already downloaded)
  ITS        — fetched fresh from NCBI (short amplicons, 200-1500 bp)

Usage:
    python scripts/build_rdna_ref.py --email your@email.com
    python scripts/build_rdna_ref.py --email your@email.com --no-fetch   # seeds only
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS_FA = REPO_ROOT / "resources" / "rrna_seeds.fa"
OUT_FA = REPO_ROOT / "resources" / "rdna_ref.fa"

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ITS amplicon queries: short sequences that cover ITS1+5.8S+ITS2
# but NOT the full SSU or LSU flanks.
ITS_QUERIES: list[tuple[str, str]] = [
    ("Alternaria[Organism] AND internal transcribed spacer[Title]", "Alternaria"),
    ("Aspergillus[Organism] AND internal transcribed spacer[Title]", "Aspergillus"),
    ("Fusarium[Organism] AND internal transcribed spacer[Title]", "Fusarium"),
    ("Agaricus[Organism] AND internal transcribed spacer[Title]", "Agaricus"),
    ("Russula[Organism] AND internal transcribed spacer[Title]", "Russula"),
    ("Rhizopus[Organism] AND internal transcribed spacer[Title]", "Rhizopus"),
]
ITS_LEN_FILTER = "200:1500[SLEN]"
N_ITS_PER_TAXON = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iter_fasta(text: str) -> Iterator[tuple[str, str]]:
    header, parts = None, []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                yield header, "".join(parts)
            header = line[1:].strip()
            parts = []
        elif line.strip():
            parts.append(line.strip())
    if header is not None:
        yield header, "".join(parts)


def classify_seed(header: str, seq_len: int) -> str | None:
    """Return 'SSU', 'ITS', or 'LSU' for a seed file header, or None to skip.

    Sequences that span SSU+ITS or ITS+LSU (full rDNA partial amplicons) are
    labelled 'ITS' when ≤1600 bp so that short ITS-region unitigs can find a
    match. The majority of the alignment for an ITS unitig will land on the ITS
    portion, not the short SSU/LSU tails.  Sequences >1600 bp carry too much
    SSU/LSU content and are classified by their dominant locus instead.
    """
    acc = header.split()[0]
    # Skip predicted mRNA sequences (code for proteins that act ON rRNA)
    if acc.startswith(("XM_", "NM_", "pdb|")):
        return None
    h = header.lower()
    if any(kw in h for kw in ("methyltransferase", "pseudouridine", "maturation", "mrna")):
        return None
    # ITS check first — many full-span records mention 28S too, but if the
    # sequence is ≤1600 bp the ITS region dominates.
    if seq_len <= 1600 and (
        "internal transcribed spacer" in h or "its1" in h or "its2" in h
    ):
        return "ITS"
    # Long sequences (>1600 bp) with ITS fall through to SSU/LSU checks below.
    if "28s ribosomal" in h or "28s rrna" in h or "large subunit ribosomal" in h:
        return "LSU"
    if "18s ribosomal" in h or "18s rrna" in h or "small subunit ribosomal" in h:
        return "SSU"
    return None


def taxon_from_header(header: str) -> str:
    """Extract first word of organism name from NCBI header."""
    parts = header.split()
    # NCBI headers: "ACCESSION.VER Genus species ..."
    if len(parts) >= 2:
        return parts[1]
    return "unknown"


def make_ref_id(locus: str, taxon: str, accession: str) -> str:
    return f"{locus}_{taxon}_{accession}"


# ---------------------------------------------------------------------------
# NCBI helpers
# ---------------------------------------------------------------------------

def entrez_search(term: str, email: str, retmax: int = 5) -> list[str]:
    params = urllib.parse.urlencode({
        "db": "nuccore",
        "term": term,
        "retmax": retmax,
        "retmode": "json",
        "email": email,
    })
    url = f"{ENTREZ_BASE}/esearch.fcgi?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": f"endophynd-rdna-ref/0.1 ({email})"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data.get("esearchresult", {}).get("idlist", [])


def entrez_fetch_fasta(uids: list[str], email: str) -> str:
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
    req = urllib.request.Request(
        url, headers={"User-Agent": f"endophynd-rdna-ref/0.1 ({email})"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Main build logic
# ---------------------------------------------------------------------------

def extract_from_seeds(seeds_fa: Path) -> list[tuple[str, str, str]]:
    """Parse rrna_seeds.fa → list of (ref_id, original_header, sequence)."""
    records = []
    with open(seeds_fa) as fh:
        for header, seq in iter_fasta(fh.read()):
            locus = classify_seed(header, len(seq))
            if locus is None:
                continue
            acc = header.split()[0]
            taxon = taxon_from_header(header)
            ref_id = make_ref_id(locus, taxon, acc)
            records.append((ref_id, header, seq))
    return records


def fetch_its(email: str) -> list[tuple[str, str, str]]:
    """Fetch ITS amplicons from NCBI → list of (ref_id, original_header, sequence)."""
    records = []
    seen_accs: set[str] = set()
    for base_term, taxon_label in ITS_QUERIES:
        term = f"({base_term}) AND {ITS_LEN_FILTER}"
        print(f"  [ITS] fetching: {taxon_label} …", end=" ", flush=True)
        try:
            uids = entrez_search(term, email, retmax=N_ITS_PER_TAXON)
            time.sleep(0.35)
            if not uids:
                print("0 hits")
                continue
            fasta_text = entrez_fetch_fasta(uids, email)
            time.sleep(0.35)
            n = 0
            for header, seq in iter_fasta(fasta_text):
                acc = header.split()[0]
                if acc in seen_accs:
                    continue
                seen_accs.add(acc)
                ref_id = make_ref_id("ITS", taxon_label, acc)
                records.append((ref_id, header, seq))
                n += 1
            print(f"{n} sequences")
        except Exception as exc:
            print(f"ERROR: {exc}")
    return records


def write_ref(records: list[tuple[str, str, str]], out_fa: Path) -> None:
    out_fa.parent.mkdir(parents=True, exist_ok=True)
    with open(out_fa, "w") as fh:
        for ref_id, orig_header, seq in records:
            fh.write(f">{ref_id}  {orig_header}\n")
            for i in range(0, len(seq), 80):
                fh.write(seq[i : i + 80] + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", help="Your email (required for NCBI fetch)")
    ap.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip NCBI; build from rrna_seeds.fa only (no ITS sequences)",
    )
    ap.add_argument(
        "--seeds", type=Path, default=SEEDS_FA,
        help=f"Seed FASTA to extract SSU/LSU from (default: {SEEDS_FA})",
    )
    ap.add_argument(
        "--out", type=Path, default=OUT_FA,
        help=f"Output reference FASTA (default: {OUT_FA})",
    )
    args = ap.parse_args()

    if not args.seeds.exists():
        print(f"[ERROR] Seed file not found: {args.seeds}")
        print("  Run: python scripts/build_rrna_seeds.py --email your@email.com")
        sys.exit(1)

    if not args.no_fetch and not args.email:
        print("[ERROR] --email is required for NCBI fetch.")
        print("  Use --no-fetch to build from seeds only (no ITS coverage).")
        sys.exit(1)

    print(f"Building rDNA BLAST reference → {args.out}")

    print(f"\n[1/2] Extracting SSU/ITS/LSU from {args.seeds}")
    seed_records = extract_from_seeds(args.seeds)
    ssu_n = sum(1 for r, _, _ in seed_records if r.startswith("SSU_"))
    its_n = sum(1 for r, _, _ in seed_records if r.startswith("ITS_"))
    lsu_n = sum(1 for r, _, _ in seed_records if r.startswith("LSU_"))
    print(f"  SSU: {ssu_n}  ITS: {its_n}  LSU: {lsu_n}")

    its_records: list[tuple[str, str, str]] = []
    if not args.no_fetch:
        print(f"\n[2/2] Fetching additional ITS amplicons from NCBI")
        its_records = fetch_its(args.email)
        print(f"  ITS from NCBI: {len(its_records)}")
    else:
        print("\n[2/2] Skipping NCBI fetch (--no-fetch); using seeds only")

    all_records = seed_records + its_records

    # Deduplicate by ref_id
    seen, deduped = set(), []
    for rec in all_records:
        if rec[0] not in seen:
            seen.add(rec[0])
            deduped.append(rec)

    locus_counts = {}
    for ref_id, _, _ in deduped:
        locus = ref_id.split("_")[0]
        locus_counts[locus] = locus_counts.get(locus, 0) + 1

    print(f"\nWriting {len(deduped)} sequences: {locus_counts}")
    write_ref(deduped, args.out)
    print(f"→ {args.out}")

    its_total = sum(1 for r, _, _ in deduped if r.startswith("ITS_"))
    if its_total == 0:
        print("\n[WARNING] No ITS sequences in reference — ITS locus assignment disabled.")
        if args.no_fetch:
            print("  Run without --no-fetch to download ITS amplicons from NCBI.")
    elif not its_records and not args.no_fetch:
        print(f"\n[NOTE] ITS coverage from seeds only ({its_total} sequences).")
        print("  Re-run with --email to supplement with NCBI ITS amplicons.")


if __name__ == "__main__":
    main()
