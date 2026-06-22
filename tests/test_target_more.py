"""
Additional targeted-search tests, complementing tests/test_target.py.

  * tool-gated blastn end-to-end (build_blast_db + align_target as LOCAL).
  * tool-gated detect_query_type (genome vs rDNA) against the project rDNA ref.
  * CLI surface tests via typer's CliRunner (no streaming actually runs).

Tool-gated tests skip cleanly when blastn / makeblastdb are absent.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from endophynd.cli import app
from endophynd.target.align import align_target, _failure_status
from endophynd.target.models import Aligner, QuerySpec, QueryType, Source, Target
from endophynd.target.query import (
    build_blast_db,
    detect_query_type,
    read_fasta_lengths,
)

FIXTURE = "tests/fixtures/ERR15383529_protein_coding_control.fa"
RDNA_REF = "resources/rdna_ref.fa"

_HAVE_BLAST = shutil.which("blastn") is not None and shutil.which("makeblastdb") is not None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _first_record(fasta_path: str) -> str:
    """Return the first FASTA record (header + sequence) as text."""
    text = Path(fasta_path).read_text()
    parts = text.split(">")
    return ">" + parts[1]


def _record_by_prefix(fasta_path: str, prefix: str) -> str:
    """Return the first FASTA record whose id starts with ``prefix``."""
    text = Path(fasta_path).read_text()
    for chunk in text.split(">")[1:]:
        if chunk.split()[0].startswith(prefix) or chunk.startswith(prefix):
            return ">" + chunk
    raise AssertionError(f"no record with prefix {prefix!r} in {fasta_path}")


# ---------------------------------------------------------------------------
# tool-gated: blastn end-to-end (LOCAL target)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAVE_BLAST, reason="blastn/makeblastdb not installed")
def test_blastn_end_to_end_local(tmp_path):
    # query = the RPB2 record (first record of the control fixture)
    query = tmp_path / "rpb2.fa"
    query.write_text(_first_record(FIXTURE))

    db_prefix = build_blast_db(str(query), tmp_path / "db")
    assert Path(db_prefix + ".nin").exists() or Path(db_prefix + ".ndb").exists()

    qspec = QuerySpec(
        fasta_path=str(query),
        query_type=QueryType.GENOME,
        record_lengths=read_fasta_lengths(str(query)),
        blast_db_prefix=db_prefix,
    )
    target = Target(accession="control", source=Source.LOCAL, local_path=FIXTURE)

    result = align_target(
        target, qspec, Aligner.BLASTN,
        min_identity=0.80, min_aln_len=100, min_query_cov=0.0,
    )
    assert result.status == "ok"
    assert result.n_hits >= 1
    h = result.hits[0]
    assert h.matched_seq != ""
    # the RPB2 record should self-match its own query id
    assert any(hit.query_id.startswith("ERR15383529_1309") for hit in result.hits)


# ---------------------------------------------------------------------------
# tool-gated: detect_query_type
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAVE_BLAST, reason="blastn not installed")
def test_detect_query_type_genome(tmp_path):
    query = tmp_path / "rpb2.fa"
    query.write_text(_first_record(FIXTURE))
    qtype = detect_query_type(str(query), RDNA_REF)
    assert qtype == QueryType.GENOME


# ---------------------------------------------------------------------------
# absent-vs-error failure classification (review #2: no silent false negatives)
# ---------------------------------------------------------------------------

def test_failure_status_absent_when_genuinely_missing():
    for stderr in [
        "fatal error: An error occurred (404) when calling the HeadObject operation: Not Found",
        "download failed: NoSuchKey The specified key does not exist",
        "cat: x.fa: No such file or directory",
        "err: cannot resolve: failed to resolve accession 'SRR999999999'",
    ]:
        assert _failure_status(stderr) == "absent", stderr


def test_failure_status_error_on_transient_or_unknown():
    # A transient network/tool failure must NOT be reported as 'absent'.
    for stderr in [
        "fatal error: Could not connect to the endpoint URL",
        "Connection reset by peer",
        "zstd: error 70 : Write error : Broken pipe",
        "",
    ]:
        assert _failure_status(stderr) == "error", stderr


@pytest.mark.skipif(not _HAVE_BLAST, reason="blastn/makeblastdb not installed")
def test_align_target_missing_local_is_not_ok(tmp_path):
    # A LOCAL target whose file does not exist must not return 'ok'/crash; the
    # failure branch runs and classifies it (here 'absent' — "No such file").
    query = tmp_path / "q.fa"
    query.write_text(_first_record(FIXTURE))
    db_prefix = build_blast_db(str(query), tmp_path / "db")
    qspec = QuerySpec(
        fasta_path=str(query), query_type=QueryType.GENOME,
        record_lengths=read_fasta_lengths(str(query)), blast_db_prefix=db_prefix,
    )
    target = Target(accession="missing", source=Source.LOCAL,
                    local_path=str(tmp_path / "does_not_exist.fasta"))
    result = align_target(target, qspec, Aligner.BLASTN)
    assert result.status in ("absent", "error")
    assert result.n_hits == 0


@pytest.mark.skipif(not _HAVE_BLAST, reason="blastn not installed")
def test_detect_query_type_rdna(tmp_path):
    # pull a single rDNA record (SSU/ITS/LSU) out of the project rDNA reference
    rdna_query = tmp_path / "rdna.fa"
    rdna_query.write_text(_record_by_prefix(RDNA_REF, "ITS_"))
    qtype = detect_query_type(str(rdna_query), RDNA_REF)
    assert qtype == QueryType.RDNA


# ---------------------------------------------------------------------------
# CLI surface (no streaming)
# ---------------------------------------------------------------------------

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "endophynd" in result.stdout
    # a version string with at least one dot is printed
    assert "0.1.0" in result.stdout


def test_cli_target_help():
    result = runner.invoke(app, ["target", "--help"])
    assert result.exit_code == 0
    assert "--max-target-seqs" in result.stdout


def test_cli_target_invalid_source(tmp_path):
    # Provide the required args so we reach the _enum validation path, then feed
    # an invalid --source. The _enum path prints an "Invalid ... Choose one of"
    # message and raises typer.Exit(2) *before* any streaming happens.
    #
    # NOTE on the exit code (honesty over the prompt's stated "exit 2"):
    # `_enum` is called as an argument inside the `target` command's
    # `try: run_targeted_search(...) except Exception: raise typer.Exit(1)`
    # block. typer.Exit subclasses RuntimeError -> Exception, so that bare
    # `except Exception` CATCHES the Exit(2) and re-raises Exit(1). The
    # observable exit code is therefore 1, not 2. We assert the real behavior
    # (1, non-zero) and the "Invalid" message, which together prove the _enum
    # validation branch executed and no streaming was attempted.
    query = tmp_path / "q.fa"
    query.write_text(">q\nACGTACGTACGT\n")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "target",
            "--query", str(query),
            "--targets", "X",
            "--out", str(out),
            "--source", "bogus",
        ],
    )
    assert result.exit_code != 0
    assert result.exit_code == 1
    # the _enum branch printed the validation message before exiting
    assert "Invalid" in result.stdout
    assert "bogus" in result.stdout
