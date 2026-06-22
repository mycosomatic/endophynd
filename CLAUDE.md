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
**Both capabilities now exercised on real data, and the discovery method is wired
into the pipeline.** Targeted search (capability B) is built, applied, and calibrated
(D27–D29). **Discovery (capability A) is validated (D30) and now promoted into the
Snakefile as real rules (D31)** — `retrieve_and_bait`(SRA: prefetch+fastq-dump+int=f)
→ `annotate_and_gate`(ITSx) → `dereplicate`(vsearch) → `classify`(blastn vs UNITE) →
`build_feature_table`(per-genus `fungal_taxa_table.tsv`). The stubs are gone; full
suite green (89) incl. the dry-run DAG test + an end-to-end fixture run.
Next: scale to all 10 GBI datasets (add the per-dataset recovery-control safeguard
first — see handoff open items from the D31 review).

**Capability A pilot (D30, 2026-06-21):** `results/gbi_its_discovery_pilot/`. A
controlled 2-dataset run (one D28 *Alternaria*-positive host, one negative) found
*Alternaria* ITS in *Silene* (positive) and none in *Streptanthus* (negative) —
independently reproducing D28 via a different molecule/data/method. Validated chain:
`prefetch`→`fastq-dump`(stream local `.sra`)→`bbduk` bait (int=f **threads=4**)→
`vsearch` derep→`ITSx`→`blastn` vs **UNITE 10.0** (≥90% id; this BLAST step — not
`sintax k:Fungi` — is the fungal discriminator). UNITE is local at
`/media/harte/extradrive1/UNITE/`; indices in `~/endophynd_cache/db/unite/`.

**Status as of 2026-06-20 (capability B):**
- **Targeted search (capability B, D27) built + validated**: `endophynd target` —
  point a query (genome/marker/rDNA) at run accessions, a BioProject, or local FASTAs;
  reference inversion (D05) streams each target through the query (minimap2 for
  genome/marker, blastn for rDNA). Package `endophynd/target/`; full test suite green.
- **First application + honest reframing (D28)**: scanned 10 GBI plant Logan datasets
  with an *Alternaria* genome → DNA matching the query in 5/10 (source undetermined —
  NOT "endophyte"). The tool answers "which datasets contain this DNA / which fungal
  DNA is in the reads," not residency. Record: `results/alternaria_vs_gbi10/REPORT.md`.
- **Specificity calibrated (D29)**: biologically-absent genome nulls (Morchella/
  Boletus/Psilocybe) + a query shuffle → false-positive floor = 0 at ≥95%/≥125 bp;
  stress sweep shows the sub-100 bp leak is conserved rDNA (not repeats). Two-tier
  reporting (≥200 high-confidence + ≥125 sensitive) + seeded-subset QC. Record:
  `results/alternaria_vs_gbi10/calibration/README.md`. Method précis: `docs/methods_summary.md`.
- **Key finding (D20)**: Logan WGS rDNA caps at ~65 bp (tandem-repeat collapse);
  single-copy genes assemble fine. ITS recovery therefore needs raw SRA reads.
- The discovery **SRA** streaming path in `rule retrieve_and_bait` landed via parallel
  work (D21/D24/D25, platform-aware); ITS primer seeds in `resources/its_primers.fa`.
- **Open**: (a) live-test `endophynd target --source sra`; (b) the GBI 5 negatives
  "any fungi?" check; (c) below-100 bp would need rDNA masking (deferred, marginal).
- **NEXT SESSION (capability A — discovery / "what's in here" from SRA ITS)**: build/
  exercise the discovery path — bait ITS from SRA reads (the merged `source=sra` path
  + `resources/its_primers.fa`), then classify against UNITE → a per-accession taxa
  table. See `docs/session_handoff.md` for the starting point and what already exists.

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
