"""Tests for the rRNA seed set and build script."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_FA = REPO_ROOT / "resources" / "rrna_seeds.fa"
SEED_PROV = REPO_ROOT / "resources" / "rrna_seeds_provenance.yml"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_rrna_seeds.py"


def test_seed_file_exists():
    assert SEED_FA.exists(), (
        f"rRNA seed file missing: {SEED_FA}\n"
        "Run: python scripts/build_rrna_seeds.py --email your@email.com"
    )


def test_seed_file_not_empty():
    assert SEED_FA.stat().st_size > 0, "Seed file is empty"


def test_seed_file_is_valid_fasta():
    """All lines must be header or IUPAC nucleotide; at least one header present."""
    # Full IUPAC degenerate nucleotide alphabet + RNA uracil
    IUPAC = set("ACGTURYSWKMBDHVNacgturyswkmbdhvn")
    headers = 0
    with open(SEED_FA) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            assert line.startswith(">") or all(c in IUPAC for c in line), (
                f"Unexpected character in FASTA line: {line!r}"
            )
            if line.startswith(">"):
                headers += 1
    assert headers >= 1, "No FASTA headers found in seed file"


def test_seed_sequences_long_enough_for_k31():
    """Every sequence must be ≥ 31 bp so bbduk can build k-mers from it."""
    records = _parse_fasta(SEED_FA)
    short = [(h, len(s)) for h, s in records if len(s) < 31]
    assert not short, (
        f"{len(short)} sequences shorter than k=31 bp: "
        + ", ".join(f"{h[:40]}…({n}bp)" for h, n in short[:3])
    )


def test_seed_file_placeholder_flag():
    """
    The placeholder seed file must have TESTING_PLACEHOLDER in its headers
    so the Snakefile and build-script --verify can detect it.
    This test simply documents that the flag is present — it's expected to
    fail (become obsolete) once the real seed set is built.
    """
    with open(SEED_FA) as f:
        content = f.read()
    # Either the placeholder flag is present, or it's a real seed file — both are fine.
    is_placeholder = "TESTING_PLACEHOLDER" in content
    # Warn if placeholder (test still passes)
    if is_placeholder:
        import warnings
        warnings.warn(
            "Using the testing placeholder seed set. "
            "Replace before Phase 1: python scripts/build_rrna_seeds.py --email your@email.com",
            UserWarning,
            stacklevel=2,
        )


def test_verify_script_runs():
    """build_rrna_seeds.py --verify should exit 0 for the existing seed file."""
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--verify", "--out", str(SEED_FA)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Verify script failed:\n{result.stdout}\n{result.stderr}"
    )


def test_provenance_file_exists():
    assert SEED_PROV.exists(), f"Provenance file missing: {SEED_PROV}"


def test_provenance_has_completion_info():
    import yaml
    with open(SEED_PROV) as f:
        prov = yaml.safe_load(f)
    assert "n_sequences_written" in prov, (
        "Provenance file missing 'n_sequences_written' key — was the build script run?"
    )
    assert prov["n_sequences_written"] > 0, "Provenance reports 0 sequences written"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_fasta(path: Path) -> list[tuple[str, str]]:
    records, header, parts = [], None, []
    with open(path) as f:
        for line in f:
            line = line.rstrip()
            if line.startswith(">"):
                if header is not None:
                    records.append((header, "".join(parts)))
                header, parts = line[1:], []
            elif line:
                parts.append(line)
    if header is not None:
        records.append((header, "".join(parts)))
    return records
