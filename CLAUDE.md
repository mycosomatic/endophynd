# Endophynd — Claude Code Instructions

## What this project is
A toolkit for recovering taxonomically relevant fungal rDNA (ITS, LSU, SSU) from
Logan/SRA data, classifying reads against multiple reference databases, and
producing metabarcoding-style reports. See `endophynd_development_plan.md` for the
full design. See `docs/decisions.md` for the append-only decision log.

## Working norms (from plan Section 0)
- Lead with honesty over agreeableness. If a request is wrong or rests on a
  mistaken assumption, say so **before** proceeding.
- Surface simpler or better-established solutions when they exist, even unprompted.
- Ask clarifying questions rather than guessing and building the wrong thing.
- Flag cost, complexity, and irreversibility risks upfront.
- Explain unfamiliar tools in plain language (deep biology knowledge; limited DevOps).
- Default to the lowest-complexity path that meets the goal.
- Do not fabricate commands, S3 paths, parameters, or figures. Verify against
  current tool docs; mark anything unverified.
- Maintain guides in `docs/guides/` as components land.
- Log every significant decision in `docs/decisions.md`.

## Current phase
Phase 0 — scaffold and decisions.
Exit criterion: empty pipeline runs end-to-end on fixtures within budget, emits a stub .qza.

## Key files
- `endophynd_development_plan.md` — full design and roadmap
- `docs/decisions.md` — decision log (append only)
- `workflow/Snakefile` — pipeline entry point
- `workflow/config/params.yml` — runtime config
- `workflow/config/cache.yml` — hot/cold/db paths + cap
- `endophynd/cache.py` — cache manager
- `endophynd/cli.py` — Typer CLI
- `tests/fixtures/` — tiny synthetic inputs

## Architecture in one paragraph
Stream compressed Logan unitigs (or SRA reads) through k-mer baiting (bbduk) to
pull candidate rDNA; annotate locus boundaries (ITSx/HMM); gate on informative
length using a calibration map; dereplicate (vsearch); classify multi-locus/multi-DB
(UNITE for ITS, SILVA for SSU/LSU, reconciled via AGGATCATTA logic); emit a QIIME2
FeatureTable + rep-seqs + taxonomy + provenance.json; delete transient accession
files. Snakemake orchestrates; per-rule conda envs reproduce locally without Docker.
Cloud is a design target, not a near-term build.

## Hardware budget
64 GB RAM, ≤200 GB hot SSD cache. Stream + process-then-delete; never land whole
raw-read or whole-unitig files.

## Subagents (under .claude/agents/)
workflow-engineer, bio-tool-integrator, benchmark-validator, test-fixtures,
reference-db-curator, reporting-viz, gui-builder, spec-keeper
