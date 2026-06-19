"""
Resolve target specifications into a concrete list of ``Target`` objects.

A target spec (one of the ``--targets`` values) can be any of:

  * a run accession           SRR1234567 / ERR15383529 / DRR000001
  * a BioProject accession    PRJNA123456 / PRJEB93827 / PRJDB1234
                              → expanded to its run accessions via the ENA
                                filereport API (no API key needed)
  * a local FASTA/FASTQ path  /path/to/genome.fa  (searched as source=local)
  * a file of specs           @accessions.txt  (one spec per line, '#' comments)
  * a comma-separated list of any of the above

Logan presence is checked (cheap S3 ``ls``) only when the source is AUTO, to
decide Logan-vs-SRA per target.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from endophynd.target.models import Source, Target

# Run accessions: SRR/ERR/DRR followed by digits.
_RUN_RE = re.compile(r"^(SRR|ERR|DRR)\d+$", re.IGNORECASE)
# BioProject accessions: PRJNA / PRJEB / PRJDB followed by digits.
_BIOPROJECT_RE = re.compile(r"^PRJ(NA|EB|DB)\d+$", re.IGNORECASE)

_FASTA_SUFFIXES = {".fa", ".fasta", ".fna", ".fq", ".fastq", ".gz", ".zst"}

ENA_FILEREPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
LOGAN_UNITIG_S3 = "s3://logan-pub/u/{acc}/{acc}.unitigs.fa.zst"


class ResolveError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# BioProject expansion (ENA)
# ---------------------------------------------------------------------------

def expand_bioproject(accession: str, timeout: float = 60.0) -> list[str]:
    """
    Return the run accessions belonging to a BioProject, via the ENA
    filereport API.  Works for ENA (PRJEB) and most NCBI (PRJNA) projects,
    which ENA cross-references.
    """
    params = urllib.parse.urlencode(
        {
            "accession": accession,
            "result": "read_run",
            "fields": "run_accession",
            "format": "tsv",
        }
    )
    url = f"{ENA_FILEREPORT}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # network / HTTP errors
        raise ResolveError(
            f"Could not expand BioProject {accession} via ENA ({url}): {e}"
        ) from e

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # First line is the header 'run_accession'.
    runs = [ln for ln in lines[1:] if ln]
    if not runs:
        raise ResolveError(
            f"BioProject {accession} returned no run accessions from ENA. "
            f"Check the accession, or that it has read_run records."
        )
    return runs


# ---------------------------------------------------------------------------
# Logan presence check
# ---------------------------------------------------------------------------

def logan_has_unitigs(accession: str, timeout: float = 60.0) -> bool:
    """
    True if Logan has a unitig file for this accession.  Cheap S3 head via
    ``aws s3 ls`` on the public bucket (no credentials).
    """
    s3 = LOGAN_UNITIG_S3.format(acc=accession)
    try:
        proc = subprocess.run(
            ["aws", "s3", "ls", s3, "--no-sign-request"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


# ---------------------------------------------------------------------------
# Spec classification
# ---------------------------------------------------------------------------

def _looks_like_fasta_path(spec: str) -> bool:
    p = Path(spec)
    if p.exists() and p.is_file():
        return True
    # Even if it doesn't exist yet, an explicit fasta-ish suffix with a path
    # separator signals "this is meant to be a file".
    return ("/" in spec or "\\" in spec) and p.suffix.lower() in _FASTA_SUFFIXES


def _read_spec_file(path: Path) -> list[str]:
    specs: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        specs.append(line)
    return specs


def _classify_one(
    spec: str,
    source: Source,
    *,
    check_logan: bool,
) -> list[Target]:
    """Turn a single, already-split spec token into one or more Targets."""
    spec = spec.strip()
    if not spec:
        return []

    # Local FASTA/FASTQ path.
    if _looks_like_fasta_path(spec):
        if not Path(spec).exists():
            raise ResolveError(f"Local target file not found: {spec}")
        return [Target(accession=Path(spec).stem, source=Source.LOCAL, local_path=spec)]

    # BioProject → expand to runs (recurse on each run accession).
    if _BIOPROJECT_RE.match(spec):
        runs = expand_bioproject(spec)
        out: list[Target] = []
        for run in runs:
            for t in _classify_one(run, source, check_logan=check_logan):
                t.bioproject = spec.upper()
                out.append(t)
        return out

    # Run accession.
    if _RUN_RE.match(spec):
        acc = spec.upper()
        resolved_source = source
        if source == Source.AUTO:
            if check_logan and logan_has_unitigs(acc):
                resolved_source = Source.LOGAN
            else:
                resolved_source = Source.SRA
        return [Target(accession=acc, source=resolved_source)]

    # Unknown shape: treat as an accession but warn (could be a non-standard id).
    sys.stderr.write(
        f"[resolve][WARN] '{spec}' is not a recognised run/BioProject accession "
        f"or local file — treating it as a raw accession.\n"
    )
    resolved = source if source != Source.AUTO else Source.SRA
    return [Target(accession=spec, source=resolved)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_targets(
    specs: list[str],
    source: Source = Source.AUTO,
    *,
    check_logan: bool = True,
) -> list[Target]:
    """
    Expand a list of target specs (each possibly comma-separated, a @file, a
    BioProject, a run accession, or a local path) into a de-duplicated list of
    Targets, preserving first-seen order.
    """
    # Flatten comma lists and @files first.
    flat: list[str] = []
    for spec in specs:
        for token in spec.split(","):
            token = token.strip()
            if not token:
                continue
            if token.startswith("@"):
                fp = Path(token[1:])
                if not fp.exists():
                    raise ResolveError(f"Spec file not found: {fp}")
                flat.extend(_read_spec_file(fp))
            else:
                flat.append(token)

    targets: list[Target] = []
    seen: set[tuple[str, str]] = set()
    for token in flat:
        for t in _classify_one(token, source, check_logan=check_logan):
            key = (t.source.value, t.local_path or t.accession)
            if key in seen:
                continue
            seen.add(key)
            targets.append(t)

    if not targets:
        raise ResolveError("No targets resolved from the given specs.")
    return targets
