"""
Informative-length gating.

Reads each annotated sequence's informative (variable) region length against
the calibration map.  Returns one of: "fine", "coarse", "discard".

  fine    — enough informative sequence for species/genus-level classification
  coarse  — enough for family/order-level; classify but note reduced resolution
  discard — too short to be meaningful

The calibration map is built by Phase 1.5 benchmarks (benchmarks/calibration/).
Until it exists, falls back to the thresholds in params.yml.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class GateDecision(str, Enum):
    FINE = "fine"
    COARSE = "coarse"
    DISCARD = "discard"


@dataclass
class RegionThreshold:
    genus_min_bp: int
    species_min_bp: int


class GateEngine:
    def __init__(
        self,
        calibration_map: dict,
        fallback_thresholds: dict,
    ):
        self.calibration_map = calibration_map  # may be empty in Phase 0
        self.fallback_thresholds = fallback_thresholds

    @classmethod
    def from_config(cls, params: dict) -> "GateEngine":
        """Build from the params.yml gate section."""
        calib_path = params["gate"].get("calibration_map")
        calibration: dict = {}
        if calib_path and Path(calib_path).exists():
            with open(calib_path) as f:
                data = yaml.safe_load(f)
                calibration = data.get("calibration", {})

        fallback = params["gate"].get("fallback_thresholds", {})
        return cls(calibration_map=calibration, fallback_thresholds=fallback)

    def decide(
        self,
        locus: str,
        informative_bp: int,
        clade: Optional[str] = None,
    ) -> GateDecision:
        """
        Return a gate decision for a read/unitig.

        Args:
            locus:          ITSx/HMM region name (e.g. "ITS1", "ITS2", "LSU", "SSU")
            informative_bp: length of the variable (non-conserved) portion
            clade:          coarse clade if known (e.g. "Ascomycota"); used to look
                            up calibration map when available
        """
        thresh = self._lookup_threshold(locus, clade)
        if thresh is None:
            return GateDecision.DISCARD

        if informative_bp >= thresh.species_min_bp:
            return GateDecision.FINE
        elif informative_bp >= thresh.genus_min_bp:
            return GateDecision.COARSE
        else:
            return GateDecision.DISCARD

    def _lookup_threshold(
        self, locus: str, clade: Optional[str]
    ) -> Optional[RegionThreshold]:
        # Try calibration map first (clade-specific)
        if self.calibration_map and locus in self.calibration_map:
            locus_data = self.calibration_map[locus]
            entry = locus_data.get(clade) or locus_data.get("default")
            if entry:
                return RegionThreshold(
                    genus_min_bp=entry["genus_min_bp"],
                    species_min_bp=entry["species_min_bp"],
                )

        # Fall back to params.yml thresholds
        fallback = self.fallback_thresholds.get(locus)
        if fallback is None:
            return None
        return RegionThreshold(
            genus_min_bp=fallback.get("coarse_min_bp", 50),
            species_min_bp=fallback.get("fine_min_bp", 100),
        )
