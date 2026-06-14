"""Tests for classify/reconcile.py."""

from endophynd.classify.reconcile import (
    TaxonAssignment,
    reconcile,
    _infer_rank,
)


def _make(locus, taxon, confidence=0.9, informative_bp=150):
    return TaxonAssignment(
        feature_id="feat_001",
        locus=locus,
        database="UNITE",
        taxon=taxon,
        confidence=confidence,
        informative_bp=informative_bp,
        gate_decision="fine",
        recovery_path="read_stub",
    )


def test_empty_returns_unclassified():
    result = reconcile([])
    assert "unclassified" in result.taxon
    assert result.resolved_rank == "unclassified"


def test_its_preferred():
    lsu = _make("LSU", "k__Fungi;p__Ascomycota;c__Sordariomycetes")
    its = _make("ITS1", "k__Fungi;p__Ascomycota;c__Sordariomycetes;o__Hypocreales;f__Nectriaceae;g__Fusarium")
    result = reconcile([lsu, its])
    assert "Fusarium" in result.taxon
    assert "ITS1" in result.supporting_loci


def test_single_assignment():
    a = _make("ITS2", "k__Fungi;p__Basidiomycota;c__Agaricomycetes")
    result = reconcile([a])
    assert result.taxon == a.taxon


def test_infer_rank_species():
    t = "k__Fungi;p__Ascomycota;c__Sordariomycetes;o__Hypocreales;f__Nectriaceae;g__Fusarium;s__oxysporum"
    assert _infer_rank(t) == "species"


def test_infer_rank_genus():
    t = "k__Fungi;p__Ascomycota;c__Sordariomycetes;o__Hypocreales;f__Nectriaceae;g__Fusarium"
    assert _infer_rank(t) == "genus"


def test_infer_rank_unclassified():
    assert _infer_rank("k__Fungi;unclassified") == "unclassified"
