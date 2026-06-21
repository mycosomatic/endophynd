"""
Tests for targeted search (capability B, `endophynd target`).

Pure-Python parser/aggregator tests use canned aligner output — fast, no tools.
The end-to-end test is gated on minimap2/blastn being present.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from endophynd.target import aggregate
from endophynd.target.align import (
    _cigar_stats,
    build_align_command,
    build_stream_command,
    parse_blastn_tab,
    parse_minimap2_sam,
)
from endophynd.target.models import (
    Aligner,
    Hit,
    QuerySpec,
    QueryType,
    Source,
    Target,
    TargetResult,
)
from endophynd.target.query import (
    choose_aligner,
    pairing_warnings,
    read_fasta_lengths,
)
from endophynd.target import resolve

FIXTURE = "tests/fixtures/ERR15383529_protein_coding_control.fa"


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------

def test_resolve_local_fasta():
    targets = resolve.resolve_targets([FIXTURE], check_logan=False)
    assert len(targets) == 1
    assert targets[0].source == Source.LOCAL
    assert targets[0].local_path == FIXTURE


def test_resolve_run_accession_sra():
    targets = resolve.resolve_targets(["SRR1234567"], source=Source.SRA, check_logan=False)
    assert targets[0].source == Source.SRA
    assert targets[0].accession == "SRR1234567"


def test_resolve_comma_split_and_dedup():
    targets = resolve.resolve_targets(
        ["ERR1111111,ERR2222222,ERR1111111"], source=Source.SRA, check_logan=False
    )
    assert [t.accession for t in targets] == ["ERR1111111", "ERR2222222"]


def test_resolve_spec_file(tmp_path):
    f = tmp_path / "accs.txt"
    f.write_text("# a comment\nERR1111111\n\nERR2222222\n")
    targets = resolve.resolve_targets([f"@{f}"], source=Source.SRA, check_logan=False)
    assert [t.accession for t in targets] == ["ERR1111111", "ERR2222222"]


def test_resolve_bioproject_expands(monkeypatch):
    monkeypatch.setattr(
        resolve, "expand_bioproject", lambda acc, timeout=60.0: ["ERR100", "ERR101"]
    )
    targets = resolve.resolve_targets(["PRJEB99999"], source=Source.SRA, check_logan=False)
    assert [t.accession for t in targets] == ["ERR100", "ERR101"]
    assert all(t.bioproject == "PRJEB99999" for t in targets)


def test_resolve_missing_local_file_errors():
    with pytest.raises(resolve.ResolveError):
        resolve.resolve_targets(["/no/such/path.fasta"], check_logan=False)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def test_read_fasta_lengths():
    lengths = read_fasta_lengths(FIXTURE)
    assert lengths["ERR15383529_1309"] == 3389   # RPB2
    assert lengths["ERR15383529_38210"] == 483   # TEF1a


def test_choose_aligner_auto():
    assert choose_aligner(QueryType.GENOME, Aligner.AUTO) == Aligner.MINIMAP2
    assert choose_aligner(QueryType.RDNA, Aligner.AUTO) == Aligner.BLASTN
    # explicit request wins
    assert choose_aligner(QueryType.RDNA, Aligner.MINIMAP2) == Aligner.MINIMAP2


def test_pairing_warning_rdna_vs_logan():
    warns = pairing_warnings(QueryType.RDNA, {Source.LOGAN})
    assert warns and "D20" in warns[0]
    assert pairing_warnings(QueryType.GENOME, {Source.LOGAN}) == []


# ---------------------------------------------------------------------------
# align: command construction
# ---------------------------------------------------------------------------

def test_stream_command_logan_is_a_pipe_no_disk():
    t = Target(accession="ERR15383529", source=Source.LOGAN)
    cmd = build_stream_command(t, to_fasta=False)
    assert "s3://logan-pub/u/ERR15383529/ERR15383529.unitigs.fa.zst" in cmd
    assert "--no-sign-request" in cmd
    assert "zstdcat" in cmd
    assert " - " in cmd  # S3 destination is stdout, not a file


def test_stream_command_sra_to_fasta():
    t = Target(accession="SRR1", source=Source.SRA)
    cmd = build_stream_command(t, to_fasta=True)
    assert "fasterq-dump" in cmd and "--stdout" in cmd
    assert "awk" in cmd  # FASTQ→FASTA conversion appended


def test_align_command_inverts_reference():
    """The query must be the reference; no dataset-side DB (D05)."""
    q = QuerySpec(fasta_path="query.fa", query_type=QueryType.GENOME, record_lengths={"q": 100})
    cmd = build_align_command("cat target.fa", Aligner.MINIMAP2, q, threads=2)
    assert "minimap2" in cmd
    assert "query.fa -" in cmd          # query indexed; dataset streamed as '-'
    assert "set -o pipefail" in cmd


def test_align_command_blastn_requires_db():
    q = QuerySpec(fasta_path="query.fa", query_type=QueryType.RDNA, record_lengths={"q": 100})
    with pytest.raises(ValueError):
        build_align_command("cat target.fa", Aligner.BLASTN, q)
    q.blast_db_prefix = "querydb"
    cmd = build_align_command("cat target.fa", Aligner.BLASTN, q)
    assert "blastn -db querydb" in cmd
    assert "/dev/stdin" in cmd


# ---------------------------------------------------------------------------
# align: parsers (canned output)
# ---------------------------------------------------------------------------

def test_cigar_stats():
    assert _cigar_stats("100M") == (100, 100)
    assert _cigar_stats("50M2D48M") == (100, 100)       # 2 deletions consume ref + block
    assert _cigar_stats("10S90M") == (90, 90)            # soft clip ignored


def _qspec(qlen=100):
    return QuerySpec(fasta_path="q.fa", query_type=QueryType.GENOME, record_lengths={"queryA": qlen})


def test_parse_minimap2_sam_basic():
    sam = ["unitig1\t0\tqueryA\t1\t60\t100M\t*\t0\t0\tACGTACGT\t*\tNM:i:5"]
    hits = parse_minimap2_sam(sam, _qspec(), min_identity=0.8, min_aln_len=50, min_query_cov=0.0)
    assert len(hits) == 1
    h = hits[0]
    assert h.matched_seq_id == "unitig1" and h.query_id == "queryA"
    assert abs(h.identity - 0.95) < 1e-9
    assert h.query_cov == 1.0
    assert h.matched_seq == "ACGTACGT"


def test_parse_minimap2_sam_skips_unmapped_and_secondary():
    sam = [
        "u1\t4\t*\t0\t0\t*\t*\t0\t0\tACGT\t*",            # unmapped
        "u2\t256\tqueryA\t1\t60\t100M\t*\t0\t0\tACGT\t*\tNM:i:0",  # secondary
    ]
    hits = parse_minimap2_sam(sam, _qspec(), min_identity=0.8, min_aln_len=50, min_query_cov=0.0)
    assert hits == []


def test_parse_minimap2_sam_identity_filter():
    sam = ["u1\t0\tqueryA\t1\t60\t100M\t*\t0\t0\tACGT\t*\tNM:i:40"]  # identity 0.60
    hits = parse_minimap2_sam(sam, _qspec(), min_identity=0.8, min_aln_len=50, min_query_cov=0.0)
    assert hits == []


def test_parse_blastn_tab_basic():
    # qseqid sseqid pident length qstart qend sstart send slen qseq
    rows = ["unitig1\tqueryA\t95.0\t100\t1\t100\t1\t100\t100\tACGTACGT"]
    hits = parse_blastn_tab(rows, _qspec(), min_identity=0.8, min_aln_len=50, min_query_cov=0.0)
    assert len(hits) == 1
    assert abs(hits[0].identity - 0.95) < 1e-9
    assert hits[0].query_cov == 1.0
    assert hits[0].matched_seq == "ACGTACGT"


def test_parse_blastn_tab_reverse_strand():
    rows = ["u1\tqueryA\t99.0\t80\t1\t80\t90\t11\t100\tACGT"]  # sstart>send
    hits = parse_blastn_tab(rows, _qspec(), min_identity=0.8, min_aln_len=50, min_query_cov=0.0)
    assert hits[0].strand == "-"
    assert hits[0].query_start == 11 and hits[0].query_end == 90


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def _result_with_hits():
    return TargetResult(
        accession="ACC1", source=Source.LOGAN, status="ok",
        hits=[
            Hit("unitig1", "queryA", 0.98, 200, 0.5, 1, 200, "ACGT"),
            Hit("unitig2", "queryA", 0.90, 150, 0.4, 250, 400, "TTTT"),
        ],
        bioproject="PRJEB1",
    )


def test_write_summary_reverse_lookup(tmp_path):
    res = [_result_with_hits()]
    path = tmp_path / "summary.tsv"
    rows = aggregate.write_summary(res, {"queryA": 400}, path)
    assert rows == 1
    lines = path.read_text().splitlines()
    assert lines[0].startswith("query_id\taccession")
    fields = lines[1].split("\t")
    assert fields[0] == "queryA" and fields[1] == "ACC1"
    assert fields[4] == "2"                 # n_hits
    assert fields[5] == "0.9800"            # best identity
    # union of [1,200] and [250,400] = 200 + 151 = 351 / 400
    assert fields[-1] == f"{351/400:.4f}"


def test_write_hit_fastas(tmp_path):
    res = [_result_with_hits()]
    n = aggregate.write_hit_fastas(res, tmp_path)
    assert n == 2
    fa = (tmp_path / "ACC1.hits.fa").read_text()
    assert ">unitig1 query=queryA" in fa
    assert "ACGT" in fa


def test_presence_matrix(tmp_path):
    res = [_result_with_hits()]
    path = tmp_path / "pm.tsv"
    aggregate.write_presence_matrix(res, ["queryA", "queryB"], path)
    lines = path.read_text().splitlines()
    assert lines[0] == "query_id\tACC1"
    assert lines[1] == "queryA\t2"
    assert lines[2] == "queryB\t0"


# ---------------------------------------------------------------------------
# end-to-end (tool-gated)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("minimap2") is None, reason="minimap2 not installed")
def test_end_to_end_local_minimap2(tmp_path):
    from endophynd.target.run import run_targeted_search

    # Use the RPB2 record as the query; the full control file as a local target.
    query = tmp_path / "rpb2.fa"
    text = Path(FIXTURE).read_text().split(">")
    rpb2 = ">" + text[1]  # first record = RPB2
    query.write_text(rpb2)

    summary = run_targeted_search(
        str(query), [FIXTURE], out_dir=str(tmp_path / "out"),
        source=Source.LOCAL, query_type=QueryType.GENOME, aligner=Aligner.MINIMAP2,
        min_aln_len=100, log=lambda *_: None,
    )
    assert summary["n_hits"] == 1
    assert summary["n_matched_sequences"] == 1
    assert (tmp_path / "out" / "targeted_summary.tsv").exists()
