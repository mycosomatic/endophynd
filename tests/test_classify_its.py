"""
Tests for the validated discovery classifier (scripts/classify_its_blast.py) and
the taxa aggregator (scripts/aggregate_taxa.py).

Core logic is exercised purely (no blastn): a feature is fungal iff it has a
passing blast hit; non-hits are 'unclassified'. Mirrors tests/test_gbi_scripts.py
in adding scripts/ to sys.path.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import classify_its_blast as cib  # noqa: E402
import aggregate_taxa as agg  # noqa: E402

UNITE = (
    "Alternaria_tenuissima|MT1|SH1.10FU|refs|"
    "k__Fungi;p__Ascomycota;c__Dothideomycetes;o__Pleosporales;"
    "f__Pleosporaceae;g__Alternaria;s__Alternaria_tenuissima"
)
DERX = (
    "Derxomyces_sp|MK2|SH2.10FU|refs|"
    "k__Fungi;p__Basidiomycota;c__Tremellomycetes;o__Tremellales;"
    "f__Bulleribasidiaceae;g__Derxomyces;s__Derxomyces_sp"
)


def test_parse_unite_lineage():
    lin = cib.parse_unite_lineage(UNITE)
    assert lin.startswith("k__Fungi")
    assert "g__Alternaria" in lin


def test_best_hits_keeps_highest_identity():
    rows = [
        ["q1", DERX, "92.0", "80", "70"],
        ["q1", UNITE, "99.0", "100", "90"],  # better -> should win
    ]
    best = cib.best_hits(rows)
    assert best["q1"][0] == 99.0
    assert best["q1"][3] == UNITE


def test_classify_fungal_and_unclassified():
    features = [("s_its1;size=5", 5), ("s_its2;size=1", 1)]
    rows = [["s_its1;size=5", UNITE, "100.0", "107", "95"]]  # only its1 hits
    recs = {r["feature_id"]: r for r in cib.classify(features, rows)}
    assert recs["s_its1;size=5"]["fungal"] == "yes"
    assert "g__Alternaria" in recs["s_its1;size=5"]["taxon"]
    # no blast hit -> not fungal (host plant / non-ITS), NOT auto-Fungi
    assert recs["s_its2;size=1"]["fungal"] == "no"
    assert recs["s_its2;size=1"]["taxon"] == "unclassified"


def test_read_features_parses_size(tmp_path):
    fa = tmp_path / "f.fa"
    fa.write_text(">s_its1;size=12\nACGT\n>s_its2;size=3\nTTTT\n")
    feats = cib.read_features(str(fa))
    assert feats == [("s_its1;size=12", 12), ("s_its2;size=3", 3)]


def test_end_to_end_via_blast_tsv(tmp_path):
    fa = tmp_path / "feat.fa"
    fa.write_text(">a;size=4\nACGTACGT\n>b;size=2\nGGGGCCCC\n")
    bt = tmp_path / "blast.tsv"
    bt.write_text(f"a;size=4\t{UNITE}\t98.5\t100\t88\n")  # only 'a' is fungal
    out = tmp_path / "tax.tsv"
    cib.main(["--features", str(fa), "--blast-tsv", str(bt), "--out", str(out)])
    lines = out.read_text().strip().splitlines()
    assert lines[0].split("\t") == cib.COLUMNS
    body = {l.split("\t")[0]: l.split("\t") for l in lines[1:]}
    assert body["a;size=4"][2] == "yes"
    assert body["b;size=2"][2] == "no"


def test_aggregate_taxa_groups_by_genus(tmp_path):
    tax = tmp_path / "tax.tsv"
    tax.write_text(
        "feature_id\tsize\tfungal\ttaxon\tpct_identity\taln_len\tunite_subject\n"
        f"a;size=5\t5\tyes\t{ '''k__Fungi;p__Ascomycota;g__Alternaria;s__x''' }\t100\t107\tX\n"
        f"b;size=3\t3\tyes\tk__Fungi;p__Ascomycota;g__Alternaria;s__y\t98\t90\tY\n"
        "c;size=9\t9\tno\tunclassified\t\t\t\n"
    )
    out = tmp_path / "table.tsv"
    agg.main(["--taxonomy", str(tax), "--out", str(out), "--min-its", "2"])
    rows = [l.split("\t") for l in out.read_text().strip().splitlines()]
    header, data = rows[0], rows[1:]
    assert header == ["rank", "name", "n_features", "read_support"]
    alt = [r for r in data if r[1] == "Alternaria"][0]
    assert alt == ["genus", "Alternaria", "2", "8"]  # 5+3 reads, 2 features; 'c' excluded
    fungal = [r for r in data if r[0] == "TOTAL" and r[1] == "fungal"][0]
    assert fungal[2] == "2" and fungal[3] == "8"
    # all_its = recovery proxy: all 3 features (incl non-fungal 'c'), 5+3+9 reads
    all_its = [r for r in data if r[0] == "TOTAL" and r[1] == "all_its"][0]
    assert all_its[2] == "3" and all_its[3] == "17"
    # 3 ITS features >= min-its 2 -> recovery_ok=yes
    rec = [r for r in data if r[0] == "recovery"][0]
    assert rec[1] == "recovery_ok" and rec[2] == "yes"


def test_recovery_ok_no_when_below_threshold(tmp_path):
    tax = tmp_path / "tax.tsv"
    # only 1 ITS feature recovered -> a "failed/low-yield" run; absence not trustworthy
    tax.write_text(
        "feature_id\tsize\tfungal\ttaxon\tpct_identity\taln_len\tunite_subject\n"
        "a;size=1\t1\tno\tunclassified\t\t\t\n"
    )
    out = tmp_path / "table.tsv"
    agg.main(["--taxonomy", str(tax), "--out", str(out), "--min-its", "10"])
    data = [l.split("\t") for l in out.read_text().strip().splitlines()[1:]]
    rec = [r for r in data if r[0] == "recovery"][0]
    assert rec[2] == "no"
