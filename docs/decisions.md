# Endophynd — Decision Log

*Append-only record of significant decisions and their rationale (ADR style). Newest entries at the bottom. This is the curated, reviewable layer of the project record — intended as supplemental material so others can audit the reasoning and spot mistakes. Raw verbatim transcripts live in `docs/transcripts/`; authoritative project state lives in git and the development plan.*

**How to use:** when a decision is made or reversed, add an entry. Keep each short. Status values: Accepted / Superseded / Revisit / Open.

**Format:**
```
### YYYY-MM-DD — <ID>: <title>
- Decision: …
- Why: …
- Alternatives considered: …
- Status: …
```

---

### 2026-05-30 — D01: Build on existing infrastructure rather than from scratch
- Decision: Center the toolkit on mature, existing tools and public resources — Logan (assembled SRA), NCBI STAT (precomputed taxonomy), phyloFlash (SSU), ITSx, vsearch, QIIME2 — and write mostly glue.
- Why: A landscape survey showed the hard parts (petabase-scale search, SRA assembly, rRNA profiling) are already solved; reinventing them is wasted effort and less reliable.
- Alternatives: Bespoke pipeline from raw reads only; branchwater (metagenome-scoped, excludes plant-genomic records).
- Status: Accepted.

### 2026-05-30 — D02: Two capabilities, one feature table
- Decision: Support discovery (blind) mode and targeted (query) mode; both produce one taxa × sample feature table, sliced two ways.
- Why: "Taxa in this plant" and "plants with this taxon" are two views of the same matrix; build once.
- Status: Accepted.

### 2026-05-30 — D03: Read-level classification is the production spine; assembly is deferred
- Decision: Classify individual reads / Logan unitigs with calibrated confidence. Assembly of baited reads and in-silico PCR are deferred experiments, off by default, gated behind QC.
- Why: rDNA is multi-copy/multi-template; assembling it is chimera-prone and untrustworthy without a QC yardstick.
- Alternatives: Assembly-first (e.g., LaBonte-style) — rejected as default due to chimera risk.
- Status: Accepted.

### 2026-05-30 — D04: Logan — prefer unitigs over contigs; Logan-first over raw reads
- Decision: Default to Logan unitigs. Use contigs only for the validation benchmark. Prefer the Logan path over downloading raw reads.
- Why: Unitigs are maximal non-branching paths — at rDNA they fragment rather than chimerize, so each is locally faithful ("a read you can trust"). Contigs resolve through branch points and can stitch one taxon's conserved region to another's variable region. Logan is ~10–100× smaller than raw reads.
- Status: Accepted (Logan trust to be quantified — see D14).

### 2026-05-30 — D05: Targeted search = reference inversion, not baiting
- Decision: For a query (single sequence or panel), make the query the tiny reference and stream the dataset through it by alignment; keep only hits. Never build a database of the dataset. Baiting is for discovery only.
- Why: Avoids downloading/storing the dataset; far more sensitive/specific for a known target than bait-then-compare. Targeted and discovery are complementary (targeted finds the query + similar; discovery catches divergent unknowns).
- Alternatives: Building a BLAST DB of the SRA (requires full download) — rejected.
- Status: Accepted.

### 2026-05-30 — D06: Gate on informative length, not read length
- Decision: Annotate each read/unitig (ITSx/HMM), measure variable (non-conserved) sequence, and gate on that; classify at the rank that length supports.
- Why: Reads dominated by conserved sequence carry little taxonomic signal; gating on informative length prevents false confidence.
- Status: Accepted (thresholds set by calibration — see D14).

### 2026-05-30 — D07: Multi-locus, multi-database classification with graceful degradation
- Decision: ITS (primary, vs UNITE), SSU (via phyloFlash, vs SILVA), LSU (vs SILVA); reconcile across loci (AGGATCATTA-style multi-DB logic); report at the resolution the locus/length supports.
- Why: ITS has the most reference data and best resolution; SSU/LSU give coarse placement when ITS is absent. ITS copy number favors its recovery (correcting an earlier wrong claim that single-copy markers are "better").
- Status: Accepted.

### 2026-05-30 — D08: Workflow engine = Snakemake
- Decision: Use Snakemake with per-rule conda environments. Nextflow set aside.
- Why: Python-native (fits the team), no Docker needed locally, runs identically on native Linux and WSL, has cloud executors for later. Nextflow's advantages are cloud/HPC-centric and don't pay off for local-first work; its DSL adds friction now.
- Alternatives: Nextflow + nf-core — revisit only if massive-scale cloud becomes the primary mode.
- Status: Accepted.

### 2026-05-30 — D09: conda environments now; containers deferred to the cloud phase
- Decision: Pin tools via per-rule conda envs locally. Containerize (Apptainer/Docker) only when reaching cloud.
- Why: Avoids imposing Docker on a cloud-novice team; rules don't change when containerized later.
- Status: Accepted.

### 2026-05-30 — D10: Output format = QIIME2 artifacts (primary), BIOM + TSV mirror
- Decision: Emit `.qza` (FeatureTable/Sequence/Taxonomy) plus BIOM/TSV. Do NOT run DADA2/Deblur — these are shotgun reads, not amplicons; features = dereplicated/clustered reads or unitigs.
- Why: The lab already uses QIIME2 for MiSeq metabarcoding; interop is nearly free.
- Status: Accepted.

### 2026-05-30 — D11: Local-first; cloud designed-for but deferred
- Decision: Build and run end-to-end on a single workstation now. Keep the design cloud-compatible (streaming, containerizable, Snakemake executors) but build no cloud infrastructure yet.
- Why: No funding/time for cloud; the finite released GBI set is local-feasible. Cloud is an executor switch later, not a redesign.
- Status: Accepted.

### 2026-05-30 — D12: Hardware budget — fit 64 GB RAM and ≤200 GB hot cache
- Decision: Design to the smaller box (64 GB RAM, ≤200 GB internal cache); external drive for cold data (DBs, results, archives). Stream compressed data through bait/alignment and process-then-delete per accession; never land whole raw-read or whole-unitig files.
- Why: Runs on both machines; streaming keeps even very large (gymnosperm) genomes within budget. Read-level path fits 64 GB comfortably; assembly (mock benchmark only, via Minia) is the lone RAM-heavy step, run on the 128 GB box.
- Status: Accepted.

### 2026-05-30 — D13: Alpha/beta diversity is a clearly-labeled "toy" feature
- Decision: Implement diversity, but only on the taxonomy-collapsed table, and label it exploratory/not quantitatively reliable everywhere it appears.
- Why: Shotgun read counts reflect coverage × rDNA copy number, not abundance; raw dereplicated-read richness is meaningless. Retained for novelty and possible future benchmarking against independent endophyte-diversity methods.
- Status: Accepted.

### 2026-05-30 — D14: Validation strategy — calibration, mock community, Logan-vs-raw concordance
- Decision: (a) Length→resolution calibration to set gating thresholds and check whether the lab's MiSeq-tuned classifier transfers to short fragments; (b) mock community built from Harte's real cultured-endophyte ITS barcodes + the Alternaria operon, spiked into a clean reference plant genome first then a real "dirty" GBI accession, with Minia (k=31) used to reproduce Logan-style assembly for ground-truth chimera measurement; (c) real-data Logan-vs-raw-SRA concordance test.
- Why: Calibration and mock precede the full classifier so thresholds are data-driven; the mock gives ground truth the real-data test cannot.
- Status: Accepted.

### 2026-05-30 — D15: Collaboration norms (honesty, humility, feedback) are part of the project
- Decision: Encode in plan Section 0: lead with honesty over agreeableness, surface simpler/better solutions, ask before building the wrong thing, flag cost/complexity risks, explain in plain language, default to lowest complexity, don't fabricate, maintain guides and this log.
- Why: The researcher is entering unfamiliar engineering/cloud territory and explicitly requested critical feedback and humility; writing it down makes Claude Code inherit it.
- Status: Accepted.

### 2026-05-30 — D16: Reproducibility & process tracking
- Decision: Use a three-layer record — git + CLAUDE.md + auto memory (continuity); exported transcripts in `docs/transcripts/` (verbatim); this `docs/decisions.md` (curated). Plus `provenance.json` per pipeline run tied to a git commit (results reproducibility).
- Why: The durable record must live on disk to survive context-window limits; a curated log is what reviewers can actually audit. Keep it lightweight.
- Status: Accepted.

### 2026-06-15 — D17: Replace ITSx with BLAST for Logan unitig locus assignment
- Decision: Use `scripts/assign_locus_blast.py` (blastn against `resources/rdna_ref.fa`) as the primary locus annotator in the `annotate_and_gate` rule, replacing ITSx.
- Why: ITSx detected 0 sequences in 226K Alternaria unitigs (ERR15383529). Root cause: ITSx requires conserved SSU/LSU flanking regions to call ITS boundaries; Logan unitigs average ~30–65 bp in rDNA-overlapping regions and contain only the variable ITS window, no flanks. BLAST aligns fragments of any length without requiring flanks.
- Alternatives considered: (a) Keep ITSx — zero recall on unitig data; (b) hmmer with ITS-only profiles — adds complexity, same flank problem; (c) BLAST (chosen) — straightforward, works at short fragment lengths, reusable for other loci.
- Status: Accepted. ITSx call preserved as commented block in Snakefile for future amplicon-length samples.

### 2026-06-15 — D18: Gate thresholds calibrated to Logan unitig lengths
- Decision: Lower fallback informative-length thresholds from amplicon-calibrated values (ITS fine=100 bp, SSU/LSU fine=200 bp) to Logan-unitig-calibrated values (ITS fine=50 bp, SSU/LSU fine=60 bp).
- Why: ERR15383529 data shows rDNA-overlapping unitigs have BLAST alignment lengths of 30–61 bp — at the k=31 assembly floor. All sequences were coarse or discard under amplicon thresholds (fine=0). At 50 bp of ITS, UNITE can classify most fungi to genus. Thresholds must match the data being processed.
- Alternatives considered: (a) Keep amplicon thresholds — 0 fine sequences, classification impossible; (b) Remove thresholds entirely — accept all BLAST hits; too permissive.
- Status: Accepted. Marked as provisional until Phase 1.5 calibration map replaces fallback values.

### 2026-06-16 — D19: ERR15383529 is ITS amplicon data; Logan unitigs are wrong tool for amplicons
- Decision: Reclassify ERR15383529 from `source=logan` to `source=sra` (pending Phase 3 SRA path). Document that Logan unitigs are inappropriate for ITS amplicon accessions.
- Why: BLAST of an ITS sequence against SRA:ERR15383529 reveals it is 151 bp PE Illumina ITS amplicon sequencing of a Collinsia plant specimen (ENA experiment ERX14787063; job title HFSONT19_4-ITS4_01-HFS-PL01-Collinsia01-NS01-1-A1-1). Raw reads are 151 bp and each spans ~27% (~153 bp) of a 568 bp ITS amplicon — fully usable for genus/species-level ID. Logan assembles these multi-species ITS reads with Minia and collapses them to 61 bp unitigs at the primer-flanking junctions because different fungal taxa share the conserved primer-adjacent bases but diverge in the ITS middle; the De Bruijn graph cannot assemble through the diversity. The raw reads are the signal; the unitigs are assembly wreckage from multi-species amplicon data.
- Root cause of short unitigs: NOT a seed or baiting problem. The seed fix (D19a, see below) still helps. The length ceiling is inherent to Minia assembly of multi-species amplicon reads.
- Decision (D19a): Removed 15 mRNA contaminant sequences from `resources/rrna_seeds.fa` (XM_/NM_ accessions for 18S rRNA processing enzymes — methyltransferases, pseudouridine synthases, maturation proteins — that slipped through the NCBI title query). Added `is_rdna()` filter to `scripts/build_rrna_seeds.py`. Seed count: 99 → 84. This eliminates false-positive baiting of protein-coding loci; it does not change the unitig length ceiling.
- Implication for pipeline design: Logan is correct for WGS accessions (full genome context; rDNA exists as part of long contigs that can extend into ITS1/ITS2 from conserved flanks). For amplicon accessions, the raw SRA reads are the feature sequences; Logan adds no value and destroys information by collapsing multi-species diversity. The samplesheet `input_type` field should encode this distinction.
- Path forward: Implement SRA raw-read streaming (Phase 3) as a first-class path. For amplicon accessions: `bbduk bait → fastp merge → annotate_and_gate` gives 200–300 bp merged amplicons at species-level resolution. The samplesheet gains `source=sra, input_type=reads` entries.
- Alternatives considered: (a) Accept 61 bp unitigs from Logan for amplicons — loses species-level resolution, only genus possible; (b) Re-assemble baited unitigs with SPAdes — chimera-prone in multi-species amplicon context, adds complexity; (c) Use Logan for WGS only (chosen) — clean separation.
- Status: Accepted. ERR15383529 updated in samplesheet to `source=sra` with note; SRA path tracked as next Phase 3 milestone.

---

### Open decisions

- **OPEN — targeted-search aligner:** minimap2 (fast, near-identity; verified Logan idiom) vs blastn with query-as-DB and reads streamed as the query (sensitive to divergence) vs mmseqs2 (middle ground). Decide by testing recall on the mock community at known query-to-target distances. (See D05.)
- **OPEN — phase ordering:** calibration+mock (Phase 1.5) before the full classifier/reporting (Phase 2) vs a rough end-to-end report first. Non-blocking.
- **OPEN — mock background:** clean reference plant genome for tuning vs a real GBI accession for realism — current plan uses clean first, then dirty as a check.
