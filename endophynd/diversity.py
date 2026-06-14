"""
Alpha/beta diversity — a clearly-labeled TOY feature.

IMPORTANT: These metrics are NOT quantitatively reliable for shotgun data.
Read counts reflect sequencing coverage × rDNA copy number, not organism
abundance; raw dereplicated-read richness is meaningless. All output from
this module must carry the caveat text from CAVEAT_TEXT below wherever it
appears in reports or logs.

Retained for novelty and as a candidate for future benchmarking against
independent endophyte-diversity methods only.

Phase 0: stubs. Real wrappers around q2-diversity in Phase 2.
"""

CAVEAT_TEXT = (
    "EXPLORATORY ONLY — NOT QUANTITATIVELY RELIABLE. "
    "Shotgun read counts reflect sequencing coverage × rDNA copy number, "
    "not organism abundance. These diversity metrics should not be used for "
    "quantitative comparisons without independent validation."
)


def alpha_diversity_stub(taxonomy_tsv: str) -> dict:
    """Placeholder: return zeroed alpha-diversity metrics."""
    return {
        "observed_features": 0,
        "shannon_entropy": 0.0,
        "caveat": CAVEAT_TEXT,
        "status": "stub — Phase 2 will implement via q2-diversity",
    }


def beta_diversity_stub(taxonomy_tsvs: list[str]) -> dict:
    """Placeholder: return empty beta-diversity result."""
    return {
        "pairwise_distances": {},
        "caveat": CAVEAT_TEXT,
        "status": "stub — Phase 2 will implement via q2-diversity",
    }
