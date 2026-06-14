"""
Workflow integration smoke test: Snakemake dry-run on the fixture samplesheet.
Requires snakemake to be installed in the test environment.
"""

import subprocess
import shutil
import pytest


@pytest.mark.skipif(
    shutil.which("snakemake") is None,
    reason="snakemake not installed in test environment",
)
def test_snakemake_dry_run(tmp_path):
    """Snakemake dry-run on the fixture config should succeed without errors."""
    result = subprocess.run(
        [
            "snakemake",
            "--configfile", "workflow/config/params.yml",
            "--cores", "1",
            "--dry-run",
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Snakemake dry-run failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
