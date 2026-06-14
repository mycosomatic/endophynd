"""
AGGATCATTA-style multi-DB taxonomy reconciliation.

Given taxonomy assignments for the same feature from multiple loci / databases,
return a single consensus assignment with a reconciled confidence.

Rules (to be refined by Phase 2 based on empirical performance):
  1. ITS is primary; if ITS gives genus+ resolution, trust it.
  2. Where ITS and LSU/SSU agree at family or above, return that rank.
  3. Where they conflict, return the higher-rank agreement; flag conflict.
  4. Unclassified at all loci → "k__Fungi;unclassified".

Phase 0: skeleton only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaxonAssignment:
    feature_id: str
    locus: str
    database: str
    taxon: str                    # full lineage string, semicolon-delimited
    confidence: float
    informative_bp: int
    gate_decision: str            # "fine" | "coarse" | "discard"
    recovery_path: str            # "read_stub" | "unitig" | "read_illumina" etc.


@dataclass
class ReconciledAssignment:
    feature_id: str
    taxon: str
    confidence: float
    resolved_rank: str            # "species" | "genus" | "family" | "order" | "unclassified"
    supporting_loci: list[str] = field(default_factory=list)
    conflict_flag: bool = False
    notes: str = ""


def reconcile(assignments: list[TaxonAssignment]) -> ReconciledAssignment:
    """
    Reconcile multiple locus/DB assignments for one feature.
    Phase 0 stub: returns the ITS assignment if present, else first assignment,
    else unclassified.
    """
    if not assignments:
        return ReconciledAssignment(
            feature_id="unknown",
            taxon="k__Fungi;unclassified",
            confidence=0.0,
            resolved_rank="unclassified",
        )

    # Prefer ITS
    its = next((a for a in assignments if a.locus.startswith("ITS")), None)
    best = its or assignments[0]

    return ReconciledAssignment(
        feature_id=best.feature_id,
        taxon=best.taxon,
        confidence=best.confidence,
        resolved_rank=_infer_rank(best.taxon),
        supporting_loci=[a.locus for a in assignments],
        notes="Phase 0 stub — no real reconciliation",
    )


def _infer_rank(taxon: str) -> str:
    """Guess the resolved rank from the depth of the lineage string.

    Tokens explicitly containing 'unclassified' are excluded from the depth
    count; if nothing meaningful remains, returns "unclassified".
    A kingdom-only classification (depth==1) is also "unclassified" for
    ecological purposes.
    """
    parts = [p.strip() for p in taxon.split(";") if p.strip() and "__" in p]
    # Exclude empty-suffix (e.g. "g__") and explicit "unclassified" tokens
    resolved = [
        p for p in parts
        if not p.endswith("__") and "unclassified" not in p.lower()
    ]
    depth = len(resolved)
    ranks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
    # kingdom-only or empty → unclassified for ecological purposes
    if depth <= 1 and "unclassified" in taxon.lower():
        return "unclassified"
    if depth == 0:
        return "unclassified"
    return ranks[min(depth - 1, len(ranks) - 1)]
