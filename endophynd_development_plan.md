# Endophynd — Development Plan

*Primary goal: **discover fungal endophytes in plant WGS genome SRA data.** Given a plant (or fungal) genome SRA accession or Logan unitig set, find which fungal taxa are present — recovering their rDNA (ITS, LSU, SSU) at the low coverage fractions typical of incidentally sequenced symbionts. Classification is **read-level**, against multiple reference databases, with output in metabarcoding-report style so results integrate with the lab's existing QIIME2 workflows.*

*Secondary capability: the same streaming pipeline supports metabarcoding amplicon SRA archives (ITS amplicon libraries) as a future extension, without changing the WGS core.*

*Revision 4 — local-first on modest hardware; cloud is a design target, not a near-term build.*

---

## 0. How we work together (for Claude, Claude Code, and Harte)

Harte is an expert mycologist and molecular biologist, and a relative newcomer to software engineering, cloud infrastructure, and large-scale data work. Any assistant working on this project should:

- **Lead with honesty over agreeableness.** If a request is demonstrably wrong, internally contradictory, or rests on a mistaken assumption, say so plainly and explain why *before* proceeding.
- **Surface simpler or better-established solutions when they exist**, even unprompted — especially patterns that are obvious from broader bioinformatics/software practice but outside Harte's current experience. Don't reinvent what a mature tool already does well.
- **Ask clarifying questions** when scope, intent, or tradeoffs are ambiguous, rather than guessing and building the wrong thing.
- **Flag cost, complexity, and irreversibility risks up front** (cloud spend, data egress, multi-hour jobs, anything hard to undo).
- **Explain unfamiliar tools and concepts in plain language** alongside the commands. Assume deep domain knowledge in biology, none in DevOps.
- **Default to the lowest-complexity path** that meets the goal; add infrastructure only when a concrete, demonstrated need justifies it.
- **Don't fabricate** exact commands, S3 paths, parameters, or figures. Verify against current tool docs; mark anything unverified.
- **Maintain the standalone how-to guides** in `docs/guides/` (Section 13) so any step can be followed without re-asking.
- **Log significant decisions and their rationale** in the decision log (Section 15) as they are made, so the process stays transparent and auditable.

This is a serious research project intended for publication; correctness and honest uncertainty matter more than momentum.

---

## 1. Objectives

### Primary use case — endophyte discovery in plant WGS

Given a plant genome SRA accession (e.g. a GBI BioProject), find which fungal endophytes are present. The sequencing library was not designed for mycology: fungal rDNA makes up a tiny fraction of a whole-genome shotgun run. The pipeline must:

1. **Bait** the small rDNA-overlapping fraction from a streaming raw-read or Logan unitig source.
2. **Filter out host plant rDNA** (18S/28S) — the most abundant baited signal and taxonomically useless for endophyte discovery.
3. **Classify each remaining read individually** and tally reads per taxon. Dereplication (the amplicon-metabarcoding idiom) is **not appropriate** here: endophyte rDNA may be present at only 1–10× coverage; there will rarely be enough identical reads to collapse meaningfully, and collapsing would destroy the absolute-count signal.
4. **Report** what fungal taxa are present and at what read-level abundance.

Raw SRA reads (`source=sra`) are required for ITS recovery: Logan's de Bruijn assembly collapses rDNA tandem repeats to ~33 bp unitigs, losing variable-region information needed for species-level classification (see D20). Logan unitigs remain valuable for protein-coding marker recovery and as a fast pre-screen.

### Two core query modes, one shared backend

- **A. Discovery (blind) mode** — given a dataset, recover all fungal rDNA present and classify it. Output: *what endophytic taxa are in this plant*.
- **B. Targeted mode** — given a query sequence (or panel, e.g. a cultured-endophyte barcode), find where it occurs across Logan / SRA. Output: *which plant accessions contain this taxon*.

Both are two slices of the same **taxa × samples table**. Build it once; answer either question by slicing it.

### Secondary capability — metabarcoding amplicon SRA archives

ITS amplicon SRA libraries (where every read is an ITS amplicon, not a random genomic fragment) are a planned extension. These use the same bait → classify core but add a fastp PE merge step to reconstruct full-length amplicons before annotation. This path is off by default; it activates via `input_type=amplicon` in the samplesheet. Do not design the WGS pipeline around amplicon assumptions.

Downstream: metabarcoding-style **reports and graphs**. **Alpha/beta diversity is included as an exploratory ("toy") feature** — implemented for novelty and future methodological comparison, but explicitly *not* quantitatively reliable (see Section 7).

### Non-negotiables
- **Read-level classification is the primary path.** Classify individual reads / Logan unitigs with calibrated confidence. Do not depend on assembly for production results.
- **Local-first.** Must run end-to-end on a single workstation, within the hardware budget in Section 6.
- **Design for eventual cloud scale-out**, but do not build cloud infrastructure now (no funding/time). Choices must not paint us into a corner.
- Maximize reuse of existing tools; minimize bespoke code.
- CLI-first; optional local Streamlit GUI on top of the same CLI.
- **QIIME2-compatible outputs** so results drop into the lab's existing metabarcoding workflow.

---

## 2. Guiding principles

1. **The feature table is the contract.** Recovery + classification produce a standardized table; analysis + reporting consume it. Primary format = **QIIME2 artifacts** (`FeatureTable[Frequency]`, `FeatureData[Sequence]`, `FeatureData[Taxonomy]`); also emit **BIOM** + plain **TSV**.
2. **Stream, never hoard.** Stream compressed data from S3 through decompression and baiting in a pipe; land only the small candidate-rDNA output. Never write whole raw-read or whole-unitig files to disk. This is what keeps us inside the disk budget.
3. **Two streaming engines, kept separate.** *Discovery* baits a dataset against conserved rDNA models to pull all rDNA — a Logan unitig file is the entire assembly (plant + everything), so it's baited just like raw reads. *Targeted* search instead **inverts the reference**: the query (one sequence or a panel) becomes the tiny reference, and the dataset streams through it by alignment, so no database of the dataset is ever built or downloaded. Baiting is for discovery only; targeted never baits. Both keep disk and compute small. Targeted finds the query and things similar enough to align; divergent unknowns are discovery's job — the two are complementary.
4. **Read-level, not assembly.** rDNA is multi-copy/multi-template; assembling it is chimera-prone. Classify reads/unitigs as individual units. Assembly is used **only** in the mock-community benchmark (to reproduce Logan's behavior with ground truth) and as a deferred experiment — never the default production path.
5. **Logan = prefer unitigs over contigs.** Unitigs are maximal non-branching paths: at rDNA they fragment rather than chimerize. Contigs resolve through branch points and can stitch one taxon's conserved region to another's variable region. Unitigs flow through the same read-level engine as raw reads; only preprocessing differs.
6. **Gate on informative length, not read length.** Annotate each read/unitig (ITSx / HMM), measure the *variable* sequence outside the conserved anchor, gate on that. The conserved region baits and orients, then steps aside.
7. **Calibrate empirically.** Know, per locus/region/clade, how much informative sequence is needed for genus vs species (Section 9). This sets gating thresholds and checks whether the lab's MiSeq-tuned classifier settings transfer to short shotgun fragments.
8. **Carry provenance everywhere.** Every feature records sample, platform, locus, recovery path (read vs unitig vs contig), database, and confidence.
9. **Graceful degradation across loci.** Report at the resolution the recovered locus/length supports (ITS → species/genus, LSU → genus/family, SSU → family/order).

---

## 3. Architecture

```
        ┌─────────────────────────────────────────────┐
        │  Interfaces                                   │
        │  • CLI (Typer) — primary                      │
        │  • Streamlit GUI — local wrapper (later)      │
        └───────────────┬─────────────────────────────┘
                        │ params (YAML) + sample sheet
        ┌───────────────▼─────────────────────────────┐
        │  Snakemake workflow                           │
        │  per-rule conda envs (no Docker locally)      │
        │  executor: local now; cloud later (same rules)│
        │  cache manager: hot cap / cold / DB dirs      │
        └───────────────┬─────────────────────────────┘
          ┌─────────────┼──────────────┬───────────────┐
          ▼             ▼              ▼               ▼
    ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────┐
    │ Triage   │  │ Retrieval│  │ READ-LEVEL│  │ Targeted    │
    │ STAT     │  │ stream   │  │ RECOVERY  │  │ search:     │
    │ metadata │  │ Logan u/ │  │ bait →    │  │ Logan-Search│
    │ rank/cut │  │ or SRA   │  │ annotate →│  │ / local idx │
    └──────────┘  │ (pipe)   │  │ gate →    │  └─────────────┘
                  └──────────┘  │ derep     │
                                └─────┬─────┘
                                      ▼
                          ┌────────────────────────┐
                          │ Classification          │
                          │ multi-locus, multi-DB   │
                          │ q2-feature-classifier + │
                          │ AGGATCATTA reconcile    │
                          │ (SSU via phyloFlash)    │
                          └───────────┬────────────┘
                                      ▼
                          ┌────────────────────────┐
                          │ FEATURE TABLE           │
                          │ QIIME2 .qza (+BIOM/TSV) │
                          │ + rep-seqs + provenance │
                          └───────────┬────────────┘
                                      ▼
                          ┌────────────────────────┐
                          │ Analysis & reporting    │
                          │ taxa bars, Krona, maps, │
                          │ (toy) diversity, HTML   │
                          └────────────────────────┘
```

### The read-level core (shared by raw reads and Logan unitigs)
```
stream input (reads OR unitigs) from S3/disk
   → k-mer bait against conserved rDNA seed models (bbduk), keep candidates only
   → annotate locus boundaries (ITSx / HMM) → split conserved vs informative
   → measure informative length → GATE (drop / coarse / fine, per calibration map)
   → dereplicate / cluster (vsearch) → features + frequencies
   → classify (q2-feature-classifier vs UNITE/SILVA; AGGATCATTA reconciliation)
   → delete the accession's transient files
```

---

## 4. Key technology decisions

### 4.1 Workflow engine — **Snakemake** *(resolved)*
Python-native (matches your background), per-rule **conda** environments (no Docker needed locally), runs identically on native Linux and WSL, and has cloud executors for the eventual scale-up. Nextflow was considered and set aside: its advantages are cloud/HPC-centric and don't pay off for local-first work, while its Groovy DSL and container-first model add friction now. Revisit Nextflow only if massive-scale cloud becomes the primary mode.

### 4.2 Reproducibility — **conda/mamba now; containers later**
Each Snakemake rule pins its tool env. Containerize (Apptainer/Docker) only when we reach the cloud phase; the rules don't change, only the deployment wrapper.

### 4.3 Data format — **QIIME2 artifacts primary; BIOM + TSV mirror**
These are shotgun reads, not amplicons: do **not** run DADA2/Deblur. Features = dereplicated/clustered baited reads (or unitigs) with frequencies.

### 4.4 CLI — **Typer**. **GUI — Streamlit** (later phase), strictly a wrapper over the CLI.

---

## 5. Tool inventory (the duct-tape map)

| Stage | Tools (reuse) | Notes |
|---|---|---|
| Workflow / orchestration | **Snakemake** + per-rule conda | local executor now; cloud later |
| Triage | NCBI STAT via cloud metadata; `sourmash` | rank/cut accessions before heavy work |
| Retrieval — Logan | `aws s3 cp … - --no-sign-request \| zstdcat` (streamed) | **unitigs** (`u/`); free public read; no AWS account |
| Retrieval — SRA | `sra-tools`; stream + bait, discard reads | local SRA path is secondary to Logan |
| Read QC / merge (Illumina) | `fastp` | trim, quality filter, merge overlapping PE |
| Baiting (streamed) | **`bbduk`** (k-mer vs rRNA seed set) primary; `SortMeRNA` alt; `barrnap` | reads from stdin → keeps only candidate rDNA; low disk/RAM |
| SSU profiling | **phyloFlash** (vs SILVA) | reuse wholesale; don't reinvent SSU |
| Per-seq locus annotation + gating | **ITSx**, HMM boundary calls | split conserved vs informative; gate on informative length |
| Dereplication / features | `vsearch` | reads/unitigs → features + frequencies (NOT ASVs) |
| Classification | **q2-feature-classifier** (UNITE for ITS), SILVA (SSU/LSU); **AGGATCATTA** multi-DB reconciliation | multi-locus, graceful degradation |
| Targeted search (query-as-reference, streamed) | index the *query* (single seq or panel); stream dataset through it — `minimap2 -a` (fast, near-identity; verified Logan idiom) **or** `blastn` with query-as-DB and reads streamed in via `<(…)` (sensitive to divergence) **or** `mmseqs2`; `rcgrep`/Logan-Search for k-mer shortlisting | **aligner = open decision (§12)**; builds no dataset-side DB |
| Diversity / stats *(toy)* | QIIME2 `q2-diversity` on taxonomy-collapsed table | **exploratory only** — see Section 7 |
| Visualization | **Plotly**, **Krona**, taxa barplots | |
| Reporting | Jinja2 → self-contained HTML; locality map | clean, minimal; agency-ready |
| **Benchmark — read simulation** | **InSilicoSeq** (or ART) | mock community at known abundances |
| **Benchmark — Logan-faithful assembly** | **Minia** (k=31), low-memory | reproduce Logan unitigs/contigs on mock for ground-truth chimera measurement |
| *(Deferred experiment)* assembly | SPAdes/metaSPAdes | off by default; chimera-prone; RAM-heavy |
| *(Deferred experiment)* in-silico PCR | `ipcress` (Exonerate), `cutadapt` | only meaningful when a sequence spans the amplicon (long reads) |

Net-new code: streaming/cache manager, read-gating logic, classifier reconciliation (reuse AGGATCATTA), feature-table/QIIME2 assembly, the benchmark harness, reporting.

---

## 6. Local execution: hardware budget, data flow, and the path to cloud

### Target hardware (design to the smaller box so it runs on both)
- **Box A:** high-end Intel (2023/24), **128 GB RAM**, limited internal SSD.
- **Box B (WSL):** similar CPU, **64 GB RAM**.
- **Budget:** fit within **64 GB RAM** and a **≤200 GB hot cache** on internal SSD. A large **external drive** holds cold data: reference DBs, finished results, and any archived inputs.

### Per-accession data flow (Logan discovery) — stays tiny
```
(optional) check unitig size from logan-pub/stats parquet; flag absurd ones
  → stream:  aws s3 cp s3://logan-pub/u/$ACC/$ACC.unitigs.fa.zst - --no-sign-request
             | zstdcat | bbduk in=stdin.fa ref=rrna_seeds.fa outm=$HOT/$ACC.baited.fa k=…
  → ITSx on $HOT/$ACC.baited.fa  (small)
  → classify → append to feature table (on cold/results dir)
  → delete $HOT/$ACC.baited.fa
```
Peak hot-cache per accession ≈ the baited set (MBs), not the whole unitig file. Parallel accessions = N × small. This is how the gymnosperm genomes (Torrey pine, cypresses — very large) stay within budget.

### Memory profile
- **Read-level path** (bait, ITSx/HMMER, vsearch, classify vs small ITS/SSU refs) peaks well under 64 GB → runs on Box B comfortably.
- **Assembly** (mock benchmark via Minia; deferred experiments) is the only memory-heavy step → run on Box A (128 GB); Minia is low-memory by design, so the mock assemblies are feasible.

### Cache manager (small, explicit)
Config keys: `hot_dir` (internal SSD, size-capped), `cold_dir` (external drive: results + archives), `db_dir` (reference DBs, can live on external). Behavior: enforce the hot cap, process-then-delete per accession, place DBs/results on cold by default. Portable across Linux and WSL (paths configurable).

### Path to cloud (designed-for, not built)
Because the workflow is Snakemake rules over containerizable tools with a streaming, per-accession data model, scaling out later means: containerize the envs, switch the Snakemake executor to a cloud/cluster backend, and run in-region with the same cost guards. No architectural change required. **Not in scope now.**

---

## 7. Outputs & analysis

Per run, a tidy results directory (plain filenames, cold/results dir):
- `feature_table.qza` (+ `.biom`, `.tsv`) — taxa × samples.
- `rep_seqs.{its,lsu,ssu}.fasta` — representative reads/unitigs per locus.
- `taxonomy.tsv` — assignment, confidence, locus, informative length, recovery path, DB.
- `provenance.json` — platform, read length, recovery path, gating thresholds, tool + DB versions per sample.
- `report.html` — composition bars, **Krona**, **locality map**, and a clearly-labeled **exploratory diversity** panel.

### Diversity is a toy feature — labeled as such
Alpha/beta diversity is computed **only on the taxonomy-collapsed table** (raw dereplicated-read richness is meaningless for shotgun data). Even collapsed, counts reflect sequencing coverage × rDNA copy number, not organism abundance, so results are semi-quantitative at best and carry the usual metabarcoding biases on top. The report must state this in plain language wherever diversity appears. It is retained for novelty and as a candidate for **future benchmarking against independent endophyte-diversity methods**, not as a reliable measurement.

---

## 8. Repository structure

```
endophynd/
├── README.md
├── pyproject.toml                 # Typer CLI, package metadata
├── envs/                          # per-rule conda env YAMLs, pinned
├── workflow/                      # Snakemake
│   ├── Snakefile
│   ├── config/                    # params.yml, samplesheet.csv, calibration_map.yml, cache config
│   ├── rules/                     # triage, retrieve, bait, annotate-gate, derep, classify, report…
│   └── envs/
├── endophynd/                     # Python package (glue + logic)
│   ├── cli.py
│   ├── cache.py                   # hot/cold/db cache manager + size cap
│   ├── dispatch.py                # platform/source detection + routing
│   ├── gate.py                    # informative-length gating (uses calibration map)
│   ├── classify/                  # AGGATCATTA-style multi-DB reconciliation
│   ├── table.py                   # QIIME2 / BIOM / TSV assembly
│   ├── report/                    # Jinja2 + Plotly + Krona + maps
│   └── diversity.py               # q2-diversity wrappers (toy)
├── benchmarks/
│   ├── mock_community/            # simulation recipes, truth sets, Minia assembly, scoring
│   ├── calibration/               # length→resolution harness + map output
│   └── logan_vs_sra/              # concordance harness
├── gui/streamlit_app.py
├── tests/fixtures/                # tiny unitigs, mock reads w/ known ITS, mini DBs
└── docs/
    ├── guides/                # standalone, beginner-friendly how-to guides (one per component)
    ├── decisions.md           # append-only decision log (ADR-style) — the supplemental record
    └── transcripts/           # exported session transcripts (Claude Code /export; chat exports)
```

---

## 9. Benchmarking & validation (the QC backbone)

Three complementary efforts; the `benchmark-validator` subagent owns all three.

1. **Length→resolution calibration.** Window UNITE references (50/75/100/125/150/200 bp × ITS1/5.8S/ITS2 × clade), classify each with the lab's QIIME2 classifier, build the **calibration map** that drives `gate.py`. Also reports whether the lab's MiSeq-tuned settings transfer to short fragments.
2. **Mock community (ground truth).** Build the truth set primarily from **Harte's own cultured-endophyte ITS barcodes** (real, already-identified isolates), supplemented with reference taxa at varying distances from the databases and the **Alternaria genome / full rDNA operon** (needed to exercise the conserved-flank baiting and SSU/LSU paths — barcodes alone yield only ITS-region reads, which is ideal for testing ITS recovery and classification). Simulate reads (InSilicoSeq/ART) from these at known low fractions (mimicking sparse endophyte signal), spiked into a **clean reference plant genome first** (clean truth), then into a **real "dirty" GBI accession** (realism check — note it carries unknown native fungi). Then:
   - run the read-level pipeline on the simulated **reads**, and
   - **assemble the same reads with Minia at k=31** (approximating how Logan builds unitigs/contigs) and run the pipeline on those.
   Score both against the truth set: sensitivity, detection limit, false positives, **chimera rate**, and resolution accuracy. This is the only place we get a ground-truth read on how much Logan-style assembly distorts results, and it sets gating + confidence thresholds on data where the right answer is known.
3. **Logan vs raw SRA concordance (real data).** For GBI genomes with both, run the pipeline on raw reads, Logan unitigs, and Logan contigs; measure concordance and flag taxa unique to contigs (chimera signature). Complements (2): behavior on real data, no ground truth.

---

## 10. Phased roadmap

Local-first; calibration and the mock community come early because they tune everything downstream.

- **Phase 0 — Scaffold & decisions.** Repo, Snakemake skeleton + conda envs, cache manager + config, feature-table/sample-sheet schemas, tiny fixtures (real GBI unitigs + synthetic reads with a known ITS). *Exit: empty pipeline runs end-to-end on fixtures within budget, emits a stub `.qza`.*
- **Phase 1 — Read-level discovery MVP (Logan unitigs).** Stream → bait → ITSx → gate → derep → classify (ITS, single DB) → QIIME2 table, with process-then-delete caching. *Exit: real taxa table from a few GBI accessions on Box B.*
- **Phase 1.5 — Calibration + mock community.** Build the calibration map and the mock harness (reads + Minia-assembled). Wire thresholds into gating. *Exit: data-driven gating; first sensitivity/chimera numbers.*
- **Phase 2 — Classification + reporting.** Multi-locus (ITS via UNITE, SSU via phyloFlash, LSU via SILVA), AGGATCATTA reconciliation, HTML report (Krona/Plotly/map) + toy diversity with caveats. *Exit: publishable-looking report from a full GBI BioProject.*
- **Phase 3 — Local raw-read recovery (Illumina).** `fastp` → bait → same core. *Exit: discovery from local/own reads, no persisted reads.*
- **Phase 3.5 — Logan vs raw SRA concordance.** Run the real-data benchmark on 1–2 genomes. *Exit: a quantified trust level for unitigs vs contigs.*
- **Phase 4 — Targeted mode (B).** Index the query (single sequence or a panel — e.g. the *Alternaria* rDNA contig plus the cultured-endophyte barcodes); stream each dataset through it by alignment; keep only hits; reverse-lookup across accessions. No baiting, no classifier required. *This engine is simpler than discovery and you already have a query — strongly consider building a minimal version as the very first MVP, ahead of or alongside Phase 1; it exercises the streaming + cache machinery with immediate real results.*
- **Phase 5 — Long-read paths.** Nanopore/PacBio detection + read-level classification (HiFi vs CLR / R9 vs R10).
- **Phase 6 — GUI.** Streamlit wrapper over the CLI: sample-sheet builder, run launcher, progress, result browser.
- **Phase 7 (deferred) — Cloud scale-out.** Containerize, switch Snakemake executor, in-region + cost guards. Only when funded/needed; design already supports it.
- **Phase 8 (experimental, optional) — Assembly / in-silico PCR for production.** Only if the mock benchmark shows it beats read-level. Off by default.

Cross-cutting: tests/CI, provenance, per-component guides, DB versioning.

---

## 11. Claude Code subagents

Define under `.claude/agents/`:

1. **`workflow-engineer`** — Snakemake rules, conda envs, executor config, the cache manager. Owns `workflow/` and `cache.py`.
2. **`bio-tool-integrator`** — wrap external CLIs (bbduk, ITSx, phyloFlash, sra-tools, vsearch, Minia, q2-* plugins): args, parsing, edge cases. Verify each against a tiny real input.
3. **`benchmark-validator`** — owns `benchmarks/`: calibration, the mock community (simulation + Minia assembly + scoring), and Logan-vs-SRA concordance. The QC backbone.
4. **`test-fixtures`** — test data, pytest, workflow stub tests, CI; tiny fixtures, fast runtimes.
5. **`reference-db-curator`** — fetch/format/version UNITE, SILVA (incl. phyloFlash's DB), lab barcodes; build the QIIME2 classifier; own the AGGATCATTA multi-DB config.
6. **`reporting-viz`** — diversity (toy, caveated), Plotly/Krona figures, HTML report, locality map.
7. **`gui-builder`** — Streamlit app, strictly a CLI wrapper.
8. **`spec-keeper`** *(optional)* — keep this plan, README, and the guides in sync as decisions change.

Start with `workflow-engineer`, `bio-tool-integrator`, `test-fixtures`, and `benchmark-validator` (Phases 0–1.5).

---

## 12. Risks & open decisions

- **Logan trust is unknown until Phases 1.5 & 3.5.** Prefer unitigs; treat contigs as suspect at rDNA. The mock (ground truth) + concordance (real) benchmarks together tell you how far to trust either. Don't publish Logan-only results before them.
- **Gating thresholds depend on calibration.** Until the map exists, gating is a guess; the lab's MiSeq-tuned classifier may not transfer to short fragments — verify.
- **Diversity is not reliable** (copy-number + coverage bias). Implemented as a toy; reports must say so.
- **Largest GBI genomes (gymnosperms) stress disk.** Mitigated by streaming + bait (never landing whole files); add a size pre-check from the Logan stats parquet and flag/skip outliers.
- **Some baited reads are uninformative** (mostly conserved). The gate handles it; track discard rate as a QC metric.
- **Reference completeness:** many dark-taxon ("Fungi sp.") calls expected for endophytes. Decide how to present these.
- **Open decision — targeted-search aligner.** `minimap2` (fast, near-identity; the verified Logan streaming idiom) vs `blastn` with the query as a tiny DB and reads streamed in as the query via `<(…)` (more sensitive to divergence) vs `mmseqs2` (sensitive middle ground). Choose by evaluation on the mock community; all are streaming and build no dataset-side database. (Engine = Snakemake; cloud deferred; containers later — all resolved.)

---

## 13. Documentation & how-to guides

A growing series of standalone, beginner-oriented guides lives in `docs/guides/`, one per component/step. Each states purpose, prerequisites, copy-pasteable commands with plain-language explanation, what success looks like, and common failure modes. As each component lands, the responsible subagent (or Claude) writes/updates its guide.

Planned guides:

- `01_getting_started.md` — dev environment + first hands-on Logan retrieval *(written)*
- `02_resolving_accessions.md` — BioProject (PRJNA) → SRA run accessions (SRR/ERR/DRR), in bulk
- `03_readlevel_core.md` — stream → bait → annotate → gate → derep → classify, locally, within budget
- `04_calibration_and_mock.md` — building the length→resolution map and the mock-community benchmark
- `05_classification_dbs.md` — UNITE/SILVA + the QIIME2 classifier; phyloFlash for SSU; AGGATCATTA config
- `06_reporting.md` — feature table → report → (toy) diversity
- `07_logan_vs_sra_validation.md` — running the concordance benchmark
- `08_scaling_local.md` — parallelizing across accessions within the cache/RAM budget
- `09_cloud_quickstart.md` — *(deferred; Phase 7)* standing up a cloud run safely, with cost guards

Lower numbers first; the cloud guide is intentionally last.

---

## 14. Immediate next steps

1. Stand up the **Phase-0 scaffold**: repo, Snakemake skeleton, conda envs, cache manager + config schema, feature-table/sample-sheet schemas.
2. Build the **rRNA seed set** for baiting (small reference of conserved SSU/5.8S/LSU sequences spanning fungal diversity).
3. Implement the **read-level discovery MVP on Logan unitigs** (Phase 1) with streaming + process-then-delete, tested on Box B.
4. Build the **calibration map + mock community** (Phase 1.5) so gating and thresholds are data-driven from the start.
5. Write guides `02`–`04` as those components land.

Move development to Claude Code, create the subagents in Section 11, and start at Phase 0.

---

## 15. Reproducibility & process tracking

Goal: keep the whole development process transparent and auditable — so reviewers with deeper expertise can spot mistakes — and durable across many iterations that far exceed any model context window. Key principle: **the durable record lives on disk, not in the model's context.** Each session rehydrates from files; nothing depends on the model "remembering." Kept deliberately light.

**1. Continuity (resume cleanly across sessions)**
- **Git** is the backbone and source of truth. Commit the plan, decision log, env lockfiles, configs; tag milestones. Survives any context limit.
- **`CLAUDE.md`** (project root) — persistent instructions Claude Code loads every session; point it at this plan and the decision log so each session rehydrates. Keep it short (a behavioral contract, not documentation).
- **Auto memory** — Claude Code accumulates its own cross-session notes automatically (on by default). A convenience; git + the plan + `decisions.md` remain authoritative.

**2. Verbatim record (raw prompts + responses, for full transparency)**
- Claude Code saves every session continuously as local transcripts (by default under `~/.claude/projects/` as JSONL), resumable via `--resume`/`--continue`; `~/.claude/history.jsonl` indexes every prompt.
- `/export` writes the current session to a plain-text file (messages + tool outputs) — drop into `docs/transcripts/` at natural breakpoints.
- For planning conversations in claude.ai, use the app's conversation export.
- These are bulky and noisy: the archive, not what reviewers read first.

**3. Curated decision log (what reviewers actually use)**
- `docs/decisions.md` — append-only, ADR-style: one short dated entry per significant decision (context, decision, rationale, alternatives, status). The high-value, low-effort artifact for catching blunders and the natural thing to attach as supplemental material. Seeded from the planning conversation.

**Results reproducibility** (separate, already in the design): every pipeline run writes `provenance.json` (tool + DB versions, params, gating thresholds, recovery path); tie each run to its git commit so any figure can be regenerated.

**Lightweight recommendation:** git + a single `docs/decisions.md` + occasional `/export` into `docs/transcripts/` + a short `CLAUDE.md`. Most of the value for little ongoing effort; add heavier tooling only if a concrete need appears.
