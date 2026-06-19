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
Phase 4 — Targeted search MVP landed (Logan + local). Two threads remain open:
(a) validate the targeted-search **SRA** streaming path on live data; (b) the
original Phase 1/3 discovery **SRA** path in `rule retrieve_and_bait`.

**Status as of 2026-06-19:**
- Phase 0 scaffold complete. Logan discovery path functional for unitigs.
- **Targeted search (capability B, D21) built**: `endophynd target` — point a
  query (genome/marker/rDNA) at run accessions, a BioProject, or local FASTAs;
  reference inversion (D05) streams each target through the query; outputs a
  reverse-lookup table + the matching unitigs/reads. Package: `endophynd/target/`.
  - minimap2 (genome) / blastn (rDNA), auto-selected; D20 caveat warns in-tool.
  - Validated on REAL Logan: RPB2 query re-found in ERR15383529 unitigs in ~12 s,
    100% identity. 23 tests pass; full suite green. Guide: `docs/guides/10_*`.
  - **SRA streaming command built but NOT yet live-tested** — next-session task.
- **Key finding (D20)**: Logan unitigs from WGS rDNA are capped at 65bp due to
  tandem repeat assembly collapse. Single-copy genes (RPB2 3389bp, RPB1 1991bp,
  TEF1a 483bp) assemble fine — confirming Logan works, rDNA is the exception.
- **Seed file cleaned (D19a)**: 15 mRNA contaminant sequences removed; 99 → 84 seeds.
- **Open next tasks**: (1) live-test `endophynd target --source sra` (fasterq-dump
  --stdout) on ERR15383529; (2) add discovery `source=sra` to `rule
  retrieve_and_bait` (see `docs/session_handoff.md`).

## Key files
- `endophynd_development_plan.md` — full design and roadmap
- `docs/decisions.md` — decision log (append only)
- `workflow/Snakefile` — discovery pipeline entry point (capability A)
- `workflow/config/params.yml` — runtime config (incl. `target:` defaults)
- `workflow/config/cache.yml` — hot/cold/db paths + cap
- `endophynd/cache.py` — cache manager
- `endophynd/cli.py` — Typer CLI (`run`, `check`, `target`, `cache`)
- `endophynd/target/` — targeted search engine (capability B): resolve, query,
  align, aggregate, run
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
