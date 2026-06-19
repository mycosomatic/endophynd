"""
Aggregate per-target hits into the targeted-search outputs.

The headline deliverable is the reverse-lookup table (D02): for each query, which
targets contain it and how strongly.  We also emit the long-form hit list, a
presence matrix, and per-target FASTAs of the actual matching unitigs/reads.
"""

from __future__ import annotations

from pathlib import Path

from endophynd.target.models import TargetResult

HITS_LONG_HEADER = [
    "accession", "source", "bioproject", "query_id", "matched_seq_id",
    "identity", "aln_len", "query_cov", "query_start", "query_end", "strand",
]

SUMMARY_HEADER = [
    "query_id", "accession", "source", "bioproject", "n_hits",
    "best_identity", "mean_identity", "max_aln_len", "max_query_cov",
    "union_query_cov",
]


def _union_len(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    intervals = sorted(intervals)
    total = 0
    lo, hi = intervals[0]
    for a, b in intervals[1:]:
        if a <= hi + 1:
            hi = max(hi, b)
        else:
            total += hi - lo + 1
            lo, hi = a, b
    total += hi - lo + 1
    return total


def write_hits_long(results: list[TargetResult], path: str | Path) -> int:
    n = 0
    with open(path, "w") as f:
        f.write("\t".join(HITS_LONG_HEADER) + "\n")
        for r in results:
            for h in r.hits:
                f.write("\t".join([
                    r.accession, r.source.value, r.bioproject or "",
                    h.query_id, h.matched_seq_id,
                    f"{h.identity:.4f}", str(h.aln_len), f"{h.query_cov:.4f}",
                    str(h.query_start), str(h.query_end), h.strand,
                ]) + "\n")
                n += 1
    return n


def write_summary(
    results: list[TargetResult],
    query_lengths: dict[str, int],
    path: str | Path,
) -> int:
    """Reverse-lookup table: one row per (query_id, accession) with ≥1 hit."""
    # group (query_id, accession) -> list of hits + context
    groups: dict[tuple[str, str], dict] = {}
    for r in results:
        for h in r.hits:
            key = (h.query_id, r.accession)
            g = groups.setdefault(key, {
                "source": r.source.value, "bioproject": r.bioproject or "",
                "identities": [], "aln_lens": [], "query_covs": [], "intervals": [],
            })
            g["identities"].append(h.identity)
            g["aln_lens"].append(h.aln_len)
            g["query_covs"].append(h.query_cov)
            g["intervals"].append((h.query_start, h.query_end))

    rows = 0
    with open(path, "w") as f:
        f.write("\t".join(SUMMARY_HEADER) + "\n")
        for (query_id, accession), g in sorted(groups.items()):
            qlen = query_lengths.get(query_id, 0)
            union_cov = (_union_len(g["intervals"]) / qlen) if qlen else 0.0
            ids = g["identities"]
            f.write("\t".join([
                query_id, accession, g["source"], g["bioproject"],
                str(len(ids)),
                f"{max(ids):.4f}", f"{sum(ids) / len(ids):.4f}",
                str(max(g["aln_lens"])), f"{max(g['query_covs']):.4f}",
                f"{union_cov:.4f}",
            ]) + "\n")
            rows += 1
    return rows


def write_presence_matrix(
    results: list[TargetResult],
    query_ids: list[str],
    path: str | Path,
) -> None:
    """Wide matrix: query_id rows × accession columns, value = n hits."""
    accessions = [r.accession for r in results]
    counts: dict[tuple[str, str], int] = {}
    for r in results:
        for h in r.hits:
            counts[(h.query_id, r.accession)] = counts.get((h.query_id, r.accession), 0) + 1

    with open(path, "w") as f:
        f.write("query_id\t" + "\t".join(accessions) + "\n")
        for q in query_ids:
            row = [str(counts.get((q, acc), 0)) for acc in accessions]
            f.write(q + "\t" + "\t".join(row) + "\n")


def write_hit_fastas(results: list[TargetResult], out_dir: str | Path) -> int:
    """Per target, write the matching unitigs/reads to <out_dir>/<label>.hits.fa."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for r in results:
        seq_hits = [h for h in r.hits if h.matched_seq]
        if not seq_hits:
            continue
        path = out_dir / f"{r.accession}.hits.fa"
        seen: set[tuple[str, str]] = set()
        with open(path, "w") as f:
            for h in seq_hits:
                key = (h.matched_seq_id, h.query_id)
                if key in seen:
                    continue
                seen.add(key)
                f.write(
                    f">{h.matched_seq_id} query={h.query_id} "
                    f"identity={h.identity:.3f} aln_len={h.aln_len} "
                    f"strand={h.strand} accession={r.accession}\n"
                )
                f.write(h.matched_seq + "\n")
                total += 1
    return total
