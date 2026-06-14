"""Tests for gate.py."""

import pytest

from endophynd.gate import GateDecision, GateEngine


FALLBACK = {
    "ITS1": {"coarse_min_bp": 50, "fine_min_bp": 100},
    "ITS2": {"coarse_min_bp": 50, "fine_min_bp": 100},
    "5.8S": {"coarse_min_bp": 0, "fine_min_bp": 0},
    "LSU":  {"coarse_min_bp": 100, "fine_min_bp": 200},
    "SSU":  {"coarse_min_bp": 100, "fine_min_bp": 200},
}


@pytest.fixture
def engine():
    return GateEngine(calibration_map={}, fallback_thresholds=FALLBACK)


def test_fine_its1(engine):
    assert engine.decide("ITS1", 150) == GateDecision.FINE


def test_coarse_its1(engine):
    assert engine.decide("ITS1", 75) == GateDecision.COARSE


def test_discard_its1(engine):
    assert engine.decide("ITS1", 20) == GateDecision.DISCARD


def test_fine_lsu(engine):
    assert engine.decide("LSU", 250) == GateDecision.FINE


def test_coarse_lsu(engine):
    assert engine.decide("LSU", 150) == GateDecision.COARSE


def test_discard_lsu(engine):
    assert engine.decide("LSU", 50) == GateDecision.DISCARD


def test_unknown_locus_discards(engine):
    # Locus not in fallback thresholds → discard
    assert engine.decide("unknown_region", 200) == GateDecision.DISCARD


def test_calibration_map_overrides_fallback():
    calibration = {
        "ITS1": {
            "Ascomycota": {"genus_min_bp": 75, "species_min_bp": 125},
        }
    }
    engine = GateEngine(calibration_map=calibration, fallback_thresholds=FALLBACK)
    # 100 bp < 125 bp species threshold → coarse
    assert engine.decide("ITS1", 100, clade="Ascomycota") == GateDecision.COARSE
    # 130 bp ≥ 125 bp → fine
    assert engine.decide("ITS1", 130, clade="Ascomycota") == GateDecision.FINE
