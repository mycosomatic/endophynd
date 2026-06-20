#!/usr/bin/env python3
"""
Summarise a targeted-search SAM into a confidence profile across three reference
classes packed into one combined reference:

  ALT_    = our target genome (the Alternaria isolate)      -> "is OUR organism here?"
  CTRL_   = a distant-fungus whole genome (S. cerevisiae)   -> cross-alignment noise floor
  FUNGAL_ = pan-fungal conserved single-copy marker panel   -> "are there ANY fungi here?"

Thresholds are class-aware on purpose:
  * "our Alternaria present"  -> hits >= STRICT_ID (0.95) over >= STRICT_ALN (500 bp);
    conspecific signal spread across the genome (breadth).
  * "any fungus present"      -> marker hits >= FUNGAL_ID (0.85) over >= FUNGAL_ALN (200 bp);
    high enough to exclude the plant host's own deep-divergent ortholog, low enough
    to catch a diverse fungus via its nearest panel member.

The SAM is parsed once at a permissive floor; all stricter cuts are computed from it.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys

from endophynd.target.align import parse_minimap2_sam
from endophynd.target.models import QuerySpec, QueryType
from endophynd.target.query import read_fasta_lengths

FLOOR_ID, FLOOR_ALN = 0.80, 200
STRICT_ID, STRICT_ALN = 0.95, 500     # "our organism" genome-presence call
FUNGAL_ID, FUNGAL_ALN = 0.85, 200     # "any fungus" marker-presence call


def _union_bp(intervals):
    if not intervals:
        return 0
    intervals = sorted(intervals)
    total, lo, hi = 0, *intervals[0]
    for a, b in intervals[1:]:
        if a <= hi + 1:
            hi = max(hi, b)
        else:
            total += hi - lo + 1
            lo, hi = a, b
    return total + hi - lo + 1


def _cls(qid: str) -> str:
    return qid.split("_", 1)[0]


def profile(ref: str, sam: str) -> dict:
    lens = read_fasta_lengths(ref)
    qs = QuerySpec(fasta_path=ref, query_type=QueryType.GENOME, record_lengths=lens)
    with open(sam) as f:
        hits = parse_minimap2_sam(f, qs, min_identity=FLOOR_ID, min_aln_len=FLOOR_ALN, min_query_cov=0.0)

    classes = {}
    for cls in ("ALT", "CTRL", "FUNGAL"):
        h = [x for x in hits if _cls(x.query_id) == cls]
        ids = sorted(x.identity for x in h)
        cls_bp = sum(v for k, v in lens.items() if _cls(k) == cls)
        # strict (our-organism) breadth
        strict = [x for x in h if x.identity >= STRICT_ID and x.aln_len >= STRICT_ALN]
        by_contig = {}
        for x in strict:
            by_contig.setdefault(x.query_id, []).append((x.query_start, x.query_end))
        breadth_bp = sum(_union_bp(v) for v in by_contig.values())
        entry = {
            "n_hits_floor": len(h),
            "n_id95_aln500": len(strict),
            "n_id85_aln200": sum(1 for x in h if x.identity >= FUNGAL_ID and x.aln_len >= FUNGAL_ALN),
            "distinct_unitigs": len({x.matched_seq_id for x in h}),
            "median_identity": round(st.median(ids), 4) if ids else 0.0,
            "max_identity": round(max(ids), 4) if ids else 0.0,
            "max_aln_len": max((x.aln_len for x in h), default=0),
            "breadth_strict_bp": breadth_bp,
            "class_bp": cls_bp,
            "breadth_strict_frac": round(breadth_bp / cls_bp, 5) if cls_bp else 0.0,
        }
        if cls == "FUNGAL":
            # which marker panel members (and thus lineages) were detected
            present = sorted({x.query_id for x in h if x.identity >= FUNGAL_ID and x.aln_len >= FUNGAL_ALN})
            entry["markers_hit"] = present
            entry["n_markers_hit"] = len(present)
        classes[cls] = entry

    return {
        "thresholds": {"floor": [FLOOR_ID, FLOOR_ALN], "strict": [STRICT_ID, STRICT_ALN],
                       "fungal": [FUNGAL_ID, FUNGAL_ALN]},
        "classes": classes,
        "alt_strict_unitig_ids": sorted({
            x.matched_seq_id for x in hits
            if _cls(x.query_id) == "ALT" and x.identity >= STRICT_ID and x.aln_len >= STRICT_ALN
        }),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--sam", required=True)
    ap.add_argument("--alt-hits-out")
    ap.add_argument("--json")
    a = ap.parse_args()

    prof = profile(a.ref, a.sam)
    alt_ids = prof.pop("alt_strict_unitig_ids")
    if a.alt_hits_out:
        with open(a.alt_hits_out, "w") as f:
            f.write("\n".join(alt_ids) + ("\n" if alt_ids else ""))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(prof, f, indent=2)

    c = prof["classes"]
    print(f"  ALT   : strict_hits={c['ALT']['n_id95_aln500']:>6} breadth={c['ALT']['breadth_strict_frac']:.4f} "
          f"med_id={c['ALT']['median_identity']:.3f} max_aln={c['ALT']['max_aln_len']}")
    print(f"  CTRL  : strict_hits={c['CTRL']['n_id95_aln500']:>6} breadth={c['CTRL']['breadth_strict_frac']:.4f}")
    print(f"  FUNGAL: markers_hit={c['FUNGAL'].get('n_markers_hit',0):>3}  "
          f"(panel members: {', '.join(m.replace('FUNGAL_','') for m in c['FUNGAL'].get('markers_hit',[])) or 'none'})")


if __name__ == "__main__":
    sys.exit(main())
