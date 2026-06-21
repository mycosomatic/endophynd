"""
Targeted search (capability B): point a query at a set of target datasets and
locate the Logan unitigs / SRA reads that match.

Public entry point: ``run_targeted_search`` in ``endophynd.target.run``.
The CLI exposes this as ``endophynd target``.

Design: reference inversion (D05) — the query is the reference; each target is
streamed through it; no dataset-side database is built or downloaded.
"""

from endophynd.target.models import (
    Aligner,
    Hit,
    QuerySpec,
    QueryType,
    Source,
    Target,
    TargetResult,
)

__all__ = [
    "Aligner",
    "Hit",
    "QuerySpec",
    "QueryType",
    "Source",
    "Target",
    "TargetResult",
]
