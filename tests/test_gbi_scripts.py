"""
Tests for the GBI helper scripts under ``scripts/`` that drive the
alignment-only confidence profile and the reverse-classification merge.

These scripts are not an installed package, so we add the repo's ``scripts/``
directory to ``sys.path`` (they themselves import the installed
``endophynd.target`` package).

Style mirrors tests/test_target.py: canned inputs, hand-built SAM/TSV, and a
subprocess invocation of the merge CLI for the end-to-end "call" logic.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import confidence_profile as cp  # noqa: E402

# merge_hit_classification parses argv at *import time* (it builds an
# ArgumentParser and calls parse_args() at module top level). Under pytest,
# sys.argv carries pytest's own flags, which argparse would reject with a
# SystemExit. Neutralise argv across the import so module load succeeds; we
# only need its pure helper (_organism_from) from the imported module — the
# end-to-end "call" logic is exercised via a subprocess with controlled argv.
_saved_argv = sys.argv
try:
    sys.argv = ["merge_hit_classification.py"]
    import merge_hit_classification as mhc  # noqa: E402
finally:
    sys.argv = _saved_argv


# ---------------------------------------------------------------------------
# confidence_profile._union_bp  (interval-union, 1-based inclusive)
# ---------------------------------------------------------------------------

def test_union_bp_empty():
    assert cp._union_bp([]) == 0


def test_union_bp_single():
    assert cp._union_bp([(5, 10)]) == 6


def test_union_bp_disjoint():
    # [1,200] -> 200, [250,400] -> 151; total 351
    assert cp._union_bp([(1, 200), (250, 400)]) == 351


def test_union_bp_adjacent_touching():
    # 101 == 100 + 1 -> intervals merge into [1,200] -> 200
    assert cp._union_bp([(1, 100), (101, 200)]) == 200


def test_union_bp_overlapping():
    assert cp._union_bp([(1, 150), (100, 200)]) == 200


def test_union_bp_nested():
    assert cp._union_bp([(1, 500), (100, 200)]) == 500


def test_union_bp_unsorted_input():
    # function sorts internally; order should not matter
    assert cp._union_bp([(250, 400), (1, 200)]) == 351


# ---------------------------------------------------------------------------
# confidence_profile._cls  (class from the id prefix)
# ---------------------------------------------------------------------------

def test_cls_prefixes():
    assert cp._cls("ALT_NODE_1") == "ALT"
    assert cp._cls("CTRL_NC_1") == "CTRL"
    assert cp._cls("FUNGAL_RPB2_X") == "FUNGAL"


# ---------------------------------------------------------------------------
# confidence_profile.profile()  (canned combined ref + canned SAM)
# ---------------------------------------------------------------------------

def _fasta_record(rec_id: str, length: int) -> str:
    # deterministic A-run sequence of the requested length, wrapped at 80 cols
    seq = "A" * length
    wrapped = "\n".join(seq[i:i + 80] for i in range(0, len(seq), 80))
    return f">{rec_id}\n{wrapped}\n"


def _sam_line(qname, rname, pos, cigar, seq, nm):
    # QNAME FLAG RNAME POS MAPQ CIGAR RNEXT PNEXT TLEN SEQ QUAL NM:i:n
    return "\t".join([
        qname, "0", rname, str(pos), "60", cigar, "*", "0", "0",
        seq, "*", f"NM:i:{nm}",
    ])


def test_profile_per_class_counts_and_markers(tmp_path):
    alt_id = "ALT_NODE_1"
    ctrl_id = "CTRL_NC_1"
    fungal_id = "FUNGAL_RPB2_x"

    ref = tmp_path / "combined_ref.fa"
    ref.write_text(
        _fasta_record(alt_id, 600)
        + _fasta_record(ctrl_id, 600)
        + _fasta_record(fungal_id, 400)
    )

    # ALT hit: 300M, NM 5 -> identity (300-5)/300 = 0.983 >= 0.95, aln 300 >= 200 (strict).
    # CTRL hit: 300M, NM 10 -> identity 0.967 >= 0.95, aln 300 (counts for CTRL class).
    # FUNGAL hit: 250M, NM 20 -> identity (250-20)/250 = 0.92 >= 0.85, aln 250 >= 200.
    sam = tmp_path / "aln.sam"
    sam.write_text(
        "@HD\tVN:1.6\tSO:unsorted\n"
        + _sam_line("u_alt", alt_id, 1, "300M", "A" * 300, 5) + "\n"
        + _sam_line("u_ctrl", ctrl_id, 1, "300M", "A" * 300, 10) + "\n"
        + _sam_line("u_fungal", fungal_id, 1, "250M", "A" * 250, 20) + "\n"
    )

    prof = cp.profile(str(ref), str(sam))
    classes = prof["classes"]

    # ALT strict hit counted in the legacy-named key.
    assert classes["ALT"]["n_id95_aln500"] == 1
    assert classes["ALT"]["n_hits_floor"] == 1
    assert classes["ALT"]["distinct_unitigs"] == 1

    # CTRL hit present at the strict cut (cross-alignment noise floor).
    assert classes["CTRL"]["n_id95_aln500"] == 1

    # FUNGAL marker detected at the 0.85/200 cut, and listed in markers_hit.
    assert classes["FUNGAL"]["n_id85_aln200"] == 1
    assert classes["FUNGAL"]["markers_hit"] == [fungal_id]
    assert classes["FUNGAL"]["n_markers_hit"] == 1

    # ALT strict unitig id surfaced for downstream collection.
    assert "u_alt" in prof["alt_strict_unitig_ids"]


def test_profile_floor_excludes_short_alignment(tmp_path):
    """A short (<200 bp) alignment is dropped at the parse floor entirely."""
    alt_id = "ALT_NODE_1"
    ref = tmp_path / "ref.fa"
    ref.write_text(_fasta_record(alt_id, 600))

    sam = tmp_path / "aln.sam"
    sam.write_text(
        _sam_line("u_short", alt_id, 1, "150M", "A" * 150, 0) + "\n"
    )
    prof = cp.profile(str(ref), str(sam))
    assert prof["classes"]["ALT"]["n_hits_floor"] == 0
    assert prof["classes"]["ALT"]["n_id95_aln500"] == 0


# ---------------------------------------------------------------------------
# merge_hit_classification._organism_from
# ---------------------------------------------------------------------------

def test_organism_from_ssciname_present():
    assert mhc._organism_from("Alternaria alternata", "anything here") == "Alternaria alternata"


def test_organism_from_strips_tpa_prefix():
    assert mhc._organism_from(
        "N/A", "TPA_asm: Bipolaris bicolor mitochondrion, complete"
    ) == "Bipolaris bicolor"


def test_organism_from_empty_title():
    assert mhc._organism_from("N/A", "") == "NO_HIT"


def test_organism_from_plain_title():
    assert mhc._organism_from(
        "N/A", "Stemphylium beticola isolate St0618 cytochrome b"
    ) == "Stemphylium beticola"


# ---------------------------------------------------------------------------
# merge_hit_classification end-to-end: the "call" classification
#   exercises _organism_from + FUNGAL_HINT + the inline call logic together.
# ---------------------------------------------------------------------------

def test_merge_call_classification_end_to_end(tmp_path):
    res = tmp_path / "res"
    hits = res / "hits"
    hits.mkdir(parents=True)

    # meta.tsv: header then one row per hit. _organism_from is not used here;
    # these columns describe the OUR-genome alignment side.
    meta_hdr = [
        "hit_id", "species", "unitig_len", "our_genome_contig",
        "our_genome_identity", "our_genome_aln_len",
    ]
    meta_rows = [
        ["hit_alt", "PlantA", "1200", "ALT_NODE_1", "0.99", "1200"],
        ["hit_fungus", "PlantA", "900", "ALT_NODE_2", "0.90", "800"],
        ["hit_bact", "PlantB", "500", "ALT_NODE_3", "0.85", "400"],
    ]
    (hits / "all_alt_hits.meta.tsv").write_text(
        "\t".join(meta_hdr) + "\n"
        + "\n".join("\t".join(r) for r in meta_rows) + "\n"
    )

    # nt blast best-hit per id: qseqid pident length evalue staxids ssciname stitle
    nt_rows = [
        # Alternaria -> call "Alternaria"
        ["hit_alt", "99.0", "1100", "0.0", "5599",
         "Alternaria alternata", "Alternaria alternata strain X genome"],
        # other fungus (Stemphylium is in FUNGAL_HINT) -> call "other_fungus"
        ["hit_fungus", "95.0", "850", "0.0", "33007",
         "N/A", "Stemphylium beticola isolate St0618 cytochrome b"],
        # bacterium, not in FUNGAL_HINT -> call "other/check"
        ["hit_bact", "88.0", "450", "0.0", "562",
         "Escherichia coli", "Escherichia coli strain K-12 chromosome"],
    ]
    (hits / "all_alt_hits.nt_blast.tsv").write_text(
        "\n".join("\t".join(r) for r in nt_rows) + "\n"
    )

    # the unitig sequences referenced by the meta hit ids
    (hits / "all_alt_hits.fa").write_text(
        ">hit_alt\nACGTACGTAC\n"
        ">hit_fungus\nTTTTGGGGCC\n"
        ">hit_bact\nGGGGCCCCAA\n"
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "merge_hit_classification.py"),
         "--res", str(res)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr

    out = (hits / "confirmed_hits.tsv").read_text().splitlines()
    header = out[0].split("\t")
    call_idx = header.index("call")
    org_idx = header.index("nt_organism")
    id_idx = header.index("hit_id")

    calls = {row.split("\t")[id_idx]: row.split("\t")[call_idx] for row in out[1:]}
    orgs = {row.split("\t")[id_idx]: row.split("\t")[org_idx] for row in out[1:]}

    assert calls["hit_alt"] == "Alternaria"
    assert calls["hit_fungus"] == "other_fungus"
    assert calls["hit_bact"] == "other/check"

    # _organism_from recovered the species from the title for the N/A row.
    assert orgs["hit_fungus"] == "Stemphylium beticola"
    assert orgs["hit_alt"] == "Alternaria alternata"
    assert orgs["hit_bact"] == "Escherichia coli"
