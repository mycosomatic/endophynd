"""
Orchestrator for targeted search (capability B).

Resolve targets → prepare the query → stream each target through the query in
parallel (process-then-delete transient files) → aggregate into the reverse-
lookup table and per-target hit FASTAs.

Public entry point: ``run_targeted_search`` (called by ``endophynd target``).
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from endophynd.target import aggregate
from endophynd.target.align import align_target
from endophynd.target.models import Aligner, QueryType, Source, TargetResult
from endophynd.target.query import pairing_warnings, prepare_query
from endophynd.target.resolve import resolve_targets


def _tool_version(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "unknown"
    except Exception:
        return "unknown"


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def run_targeted_search(
    query_path: str,
    target_specs: list[str],
    *,
    out_dir: str,
    source: Source = Source.AUTO,
    query_type: QueryType = QueryType.AUTO,
    aligner: Aligner = Aligner.AUTO,
    rdna_ref: str = "resources/rdna_ref.fa",
    min_identity: float = 0.80,
    min_aln_len: int = 50,
    min_query_cov: float = 0.0,
    minimap2_preset: str = "asm20",
    max_target_seqs: int = 5,
    evalue: float = 1e-5,
    jobs: int = 4,
    threads: int = 4,
    check_logan: bool = True,
    log=print,
) -> dict:
    """
    Run a full targeted search and write outputs to ``out_dir``.  Returns a
    summary dict (also persisted as provenance.json).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "run.log"

    # --- Resolve targets -----------------------------------------------------
    log(f"[target] resolving {len(target_specs)} target spec(s)…")
    targets = resolve_targets(target_specs, source=source, check_logan=check_logan)
    sources = {t.source for t in targets}
    log(f"[target] {len(targets)} target(s); sources = {sorted(s.value for s in sources)}")

    # --- Prepare query (transient workdir for any BLAST DB) ------------------
    workdir = Path(tempfile.mkdtemp(prefix="endophynd_target_", dir=str(out)))
    try:
        query_spec, resolved_aligner = prepare_query(
            query_path, query_type=query_type, aligner=aligner,
            rdna_ref=rdna_ref, workdir=workdir,
        )
        log(
            f"[target] query: {len(query_spec.record_lengths)} record(s), "
            f"{query_spec.total_bp} bp; type={query_spec.query_type.value}; "
            f"aligner={resolved_aligner.value}"
        )

        # Honest pairing warnings (e.g. rDNA query vs Logan, D20).
        for w in pairing_warnings(query_spec.query_type, sources):
            log(f"[target][WARN] {w}")

        # --- Stream each target through the query (parallel) -----------------
        results: list[TargetResult] = []

        def _work(t):
            return align_target(
                t, query_spec, resolved_aligner,
                threads=threads, minimap2_preset=minimap2_preset,
                min_identity=min_identity, min_aln_len=min_aln_len,
                min_query_cov=min_query_cov, max_target_seqs=max_target_seqs,
                evalue=evalue, log_path=log_path,
            )

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            futures = {ex.submit(_work, t): t for t in targets}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    r = fut.result()
                except Exception as e:  # never let one target sink the run
                    r = TargetResult(
                        accession=t.accession, source=t.source, status="error",
                        message=str(e), bioproject=t.bioproject,
                    )
                results.append(r)
                log(
                    f"[target] {r.accession} ({r.source.value}): "
                    f"{r.status}, {r.n_hits} hit(s)"
                )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)  # process-then-delete

    # Keep target order stable (resolution order) for the outputs.
    order = {t.accession: i for i, t in enumerate(targets)}
    results.sort(key=lambda r: order.get(r.accession, 1 << 30))

    # --- Write outputs -------------------------------------------------------
    query_ids = list(query_spec.record_lengths.keys())
    n_hits = aggregate.write_hits_long(results, out / "targeted_hits.tsv")
    n_pairs = aggregate.write_summary(results, query_spec.record_lengths, out / "targeted_summary.tsv")
    aggregate.write_presence_matrix(results, query_ids, out / "presence_matrix.tsv")
    n_seqs = aggregate.write_hit_fastas(results, out / "per_target")

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    summary = {
        "tool": "endophynd target",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": _git_sha(),
        "query": {
            "path": query_path,
            "type": query_spec.query_type.value,
            "n_records": len(query_ids),
            "total_bp": query_spec.total_bp,
        },
        "aligner": resolved_aligner.value,
        "params": {
            "source": source.value,
            "min_identity": min_identity,
            "min_aln_len": min_aln_len,
            "min_query_cov": min_query_cov,
            "minimap2_preset": minimap2_preset,
            "max_target_seqs": max_target_seqs,
            "evalue": evalue,
        },
        "n_targets": len(results),
        "target_status": status_counts,
        "n_hits": n_hits,
        "n_query_target_pairs": n_pairs,
        "n_matched_sequences": n_seqs,
        "tool_versions": {
            "minimap2": _tool_version(["minimap2", "--version"]),
            "blastn": _tool_version(["blastn", "-version"]),
        },
        "outputs": {
            "summary": str(out / "targeted_summary.tsv"),
            "hits_long": str(out / "targeted_hits.tsv"),
            "presence_matrix": str(out / "presence_matrix.tsv"),
            "hit_fastas_dir": str(out / "per_target"),
        },
    }
    with open(out / "provenance.json", "w") as f:
        json.dump(summary, f, indent=2)

    log(
        f"[target] done: {n_hits} hit(s) across {n_pairs} query×target pair(s); "
        f"{n_seqs} matching sequence(s) saved. Outputs in {out}"
    )
    return summary
