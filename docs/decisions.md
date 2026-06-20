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

### 2026-06-16 — D20: Logan rDNA failure confirmed as tandem-repeat assembly collapse; Logan vindicated for single-copy genes
- Decision: Keep Logan as primary source for WGS accessions; add SRA raw-read path for ITS recovery. Do NOT abandon Logan.
- Evidence: Protein-coding control experiment on ERR15383529 (Alternaria alternata WGS PE150). Single-copy genes assemble into long unitigs from the same Logan file where ITS gives only 65bp: RPB2 → 3389bp, RPB1 → 1991bp, TEF1a → 483bp. ITS → 65bp max. The failure is 100% specific to the rDNA tandem repeat array, not Logan, not the baiting strategy, not the seeds.
- Why tandem repeats fail: The fungal rDNA operon occurs in 10–80 tandem copies per genome (~7kb each). PE150 reads cannot span repeat unit boundaries. In the De Bruijn graph, all identical k-mers from multiple copies collapse to a single node and form cyclic paths Minia cannot resolve. The only escape is at the repeat/unique junction — producing 65bp tip unitigs at the conserved primer-flanking sites.
- Implication: Logan IS the right tool for (a) finding Alternaria in a plant genome (TEF1a, RPB2, RPB1 will bait), (b) non-rDNA discovery in WGS accessions, (c) metagenomic samples where target is not multi-copy. ITS requires raw reads from SRA.
- Control sequences saved to tests/fixtures/ERR15383529_protein_coding_control.fa.
- Status: Accepted. Phase 3 SRA path elevated to next milestone; Logan path unchanged for protein-coding.

### 2026-06-16 — D21: Implement source=sra in triage and retrieve_and_bait rules
- Decision: Add `source=sra` branch to both rules using `fasterq-dump --stdout --split-spot --skip-technical --threads N | bbduk.sh in=stdin.fq`. Set `minlength=100` (was 50) as the post-bait length floor.
- Why: Follows directly from D19/D20. `fasterq-dump --stdout` streams FASTQ without landing the full file on disk; `--split-spot` interleaves PE reads so bbduk sees each read independently. `minlength=100` is a safe floor for PE151 reads; the previous 50 was ineffective for Logan FASTA stdin anyway (handoff note #4, no regression). `bbduk.sh in=stdin.fq` (not `stdin.fa`) signals FASTQ input; output is still `.baited.fa` (bbduk converts to FASTA by output extension).
- Alternatives considered: (a) `fastq-dump --stdout --split-spot` — true streaming but slower; fasterq-dump is the current NCBI recommendation; (b) download full FASTQ first then pipe — violates D12 streaming constraint.
- Status: Accepted.

### 2026-06-16 — D22: Correction — ERR15383529 is Alternaria alternata WGS, not Collinsia ITS amplicon
- Decision: Retract the species/experiment identification in D19. ERR15383529 is Alternaria alternata WGS 42x PE151.
- Why D19 was wrong: A previous session BLASTed Collinsia endophyte ITS sequences (the query) against ERR15383529 (the target) and mistakenly concluded the accession itself was Collinsia ITS amplicon data. The query and target were confused. ERR15383529 is Alternaria WGS; the Collinsia sequences are the researcher's own endophyte barcodes used as a BLAST probe.
- What stands from D19: The core decision (switch ERR15383529 to source=sra; raw reads needed for ITS because Logan tandem-repeat collapse produces only 33bp unitigs at rDNA) remains valid — for the correct reason (rDNA tandem-repeat assembly collapse in Alternaria WGS, as confirmed by the protein-coding control in D20).
- Status: Accepted. samplesheet.csv notes corrected.

### 2026-06-16 — D23: Primary use case is endophyte discovery in plant WGS; dereplicate step removed from WGS path
- Decision: Clarify in the development plan that the primary purpose of endophynd is finding fungal endophytes in plant WGS genome SRA data. As a consequence: (a) dereplication (vsearch) is removed from the WGS pipeline; (b) a host plant rDNA filter step is required before classification; (c) each baited read is classified individually and tallied by taxon.
- Why no derep: Amplicon metabarcoding dereplicates because 50,000 reads may be identical copies of one amplicon — collapsing to a representative + count is necessary before classification. For WGS endophyte discovery, endophyte rDNA is present at 1–10× coverage; there are very few identical reads per taxon, nothing meaningful to collapse, and the absolute read count per taxon is itself the signal. Dereplication would destroy information rather than compress it.
- Why host filter: Host plant rDNA (18S, 28S) will be the most abundant hit after baiting — the plant's own ~1000 rDNA copies dominate. These must be removed before classification or the output is dominated by the host.
- Amplicon archives: metabarcoding SRA libraries remain a planned secondary capability, gated by input_type=amplicon in the samplesheet. They use the same bait core plus fastp PE merge, and dereplication is appropriate there. The WGS pipeline is not designed around amplicon assumptions.
- Status: Accepted. Development plan updated (Revision 4).

### 2026-06-16 — D24: Two-path recovery — ITS via SRA raw reads; protein-coding via Logan unitigs
- Decision: The blind discovery pipeline uses two complementary paths. Path A: stream SRA raw reads → bait with fungal-specific ITS primer k-mers → classify against UNITE → species/genus level. Path B: stream Logan unitigs → bait with fungal protein-coding marker seeds (RPB2, RPB1, TEF1a, β-tubulin) → classify against protein-coding reference DB → genus/family level.
- Why ITS needs SRA: Logan collapses rDNA tandem repeats to ~33bp unitigs (D20). ITS variable-region information is destroyed. Full-length SRA reads (PE151) span the ITS region and classify to species with UNITE.
- Why protein-coding uses Logan: Single-copy genes assemble to full-length unitigs in Logan (RPB2 → 3389bp, RPB1 → 1991bp, TEF1a → 483bp confirmed on ERR15383529). No tandem-repeat collapse. Logan data is 10–100× smaller than raw reads, making it practical to screen all of Logan without downloading SRA files for every accession. Coarser resolution (genus/family) acceptable for this scale.
- Why fungal-specific primers as bait seeds: Generic conserved rDNA seeds (SSU, LSU) bait host plant rDNA as the dominant signal. Fungal-specific primers (ITS1-F, ITS3-KYO variants, etc.) select reads overlapping primer binding sites that are enriched in Fungi, reducing host contamination at the baiting stage.
- Status: Accepted. Supersedes the single-path rDNA baiting design in Revision 3 of the development plan.

### 2026-06-16 — D25: Platform-aware quality tiers for SRA streaming
- Decision: Branch the SRA retrieval path on the samplesheet `platform` field. Four supported values: `illumina`, `pacbio-hifi`, `pacbio-clr`, `ont`. Each sets different minlength, quality floor, and pairing behaviour in the bbduk bait step. Classification resolution is capped per platform in provenance.
- Tiers:
  - `illumina`: `--split-spot`, `int=t` (bait-then-mate), minlength=100, no quality floor. Species-level classification appropriate.
  - `pacbio-hifi` (CCS): single-end, minlength=500, minavgquality=30. Q30-40 reads; species-level classification appropriate.
  - `pacbio-clr`: single-end, minlength=500, minavgquality=15. Q10-15; genus-level only — do not report species calls.
  - `ont`: single-end, minlength=500, minavgquality=15. Q10-30 (highly variable by chemistry/basecaller); genus-level default; species calls flagged if measured median Q<20.
- Why Q25-30 threshold for species: at Q25 a 600bp ITS read averages ~2 errors — within UNITE's 97% identity threshold for species assignment. Below Q20 (~6+ errors per 600bp) species calls are unreliable.
- Why ONT is not automatically genus-only: R10.4.1 with duplex basecalling reaches Q25-35, suitable for species. The pipeline measures actual read quality after baiting and flags, rather than hard-capping all ONT.
- Status: Accepted. Implemented in triage (platform validation) and retrieve_and_bait (per-platform shell branch).

### 2026-06-16 — D26: Comprehensive step-by-step logging for reproducibility
- Decision: Every run must produce a complete audit trail sufficient to re-run any step manually. Implemented via three layers: (1) `run.sh` wrapper that runs Snakemake with `--printshellcmds --reason` and tees all output to a timestamped log at `$RESULTS/snakemake_${STAMP}.log`, recording git commit, branch, host, and tool versions in the header; (2) per-rule audit headers in the `triage` and `retrieve_and_bait` log files, recording start timestamp, seed file md5, tool versions (fasterq-dump, bbduk), platform settings, and bait yield (total_reads, matched, match_pct, seqs_out); (3) enhanced `provenance.json` with git branch, seed file md5 checksums, snakemake/python versions, and per-sample bait stats parsed from the rule logs.
- Auxiliary tool: `scripts/log_versions.sh` — standalone script to snapshot all tool versions across all conda environments and reference file checksums; designed to be run once before a production run and archived.
- Why three layers: The Snakemake log from `run.sh` captures every shell command and its exit code — the "what ran". The per-rule logs capture the "what parameters and what inputs" at execution time. The `provenance.json` collects everything into a single machine-readable file per run for downstream auditing. Together they allow a step to be replicated by copy-pasting commands from the Snakemake log with parameters cross-referenced from the rule logs.
- Why rule logs live in cold storage: Cold storage (`COLD/logs/`) is never deleted by `cleanup_transient`, so rule logs persist long after hot-cache baited files are removed. The `provenance` rule reads bait stats from cold-storage logs, not from hot-cache bait_stats files.
- Status: Accepted. Implemented in run.sh, scripts/log_versions.sh, workflow/Snakefile (triage and retrieve_and_bait audit headers, enhanced provenance rule).

### 2026-06-19 — D27: Targeted search (Phase 4, capability B) — first MVP, built as a standalone CLI engine
- Decision: Implement `endophynd target` as a self-contained Python engine + Typer subcommand (package `endophynd/target/`), *outside* the samplesheet-driven Snakemake discovery flow. It points a query (genome, single-copy markers, or rDNA barcode) at a set of targets (run accessions, a BioProject, or local FASTAs) and locates the Logan unitigs / SRA reads that match, by reference inversion (D05): the query is the reference; each target is streamed through it; no dataset-side database is built or downloaded.
- Why a standalone CLI engine rather than Snakemake rules: the target set is *dynamic* (BioProject → runs resolved at runtime), which fits Snakemake's static DAG poorly (would need checkpoints). The plan's architecture already shows targeted search as its own branch, not a samplesheet flow. CLI-first is the lowest-complexity path that meets the goal and matches the project's "CLI-first; GUI wraps it" stance. It reuses the existing Logan streaming idiom and CacheManager-style process-then-delete. A Snakemake wrapper can come later without redesign.
- Aligner: ship both, auto-selected by query type — minimap2 for genome/marker queries (fast, near-identity; the verified Logan idiom), blastn for rDNA/divergent queries (sensitive, length-agnostic, and emits the aligned dataset sequence via `qseq`). Both stream the dataset through the query and build no dataset-side DB. Swappable via `--aligner`. (Updates the OPEN aligner decision; final single-aligner call still pending mock-community calibration — §12.)
- Query type drives source warnings (the D20 honesty caveat is built into the tool): an rDNA query against Logan unitigs prints a warning that Logan collapses the rDNA array to ~65 bp and recommends `--source sra`. Auto-detection aligns the query against `resources/rdna_ref.fa` (rDNA if ≥40% of query bp aligns).
- Sources: Logan unitigs (built + validated on real data), local FASTA (built + validated), SRA reads via `fasterq-dump --stdout` (command built; not yet validated on a live SRA stream — flagged for the next session). `--source auto` prefers Logan when the accession is present in the bucket, else SRA.
- Outputs: `targeted_summary.tsv` (reverse-lookup table — the headline: which targets contain each query, with best/mean identity and union query coverage), `targeted_hits.tsv` (long form), `presence_matrix.tsv` (query × accession hit counts), `per_target/<acc>.hits.fa` (the actual matching unitigs/reads), and `provenance.json`.
- Validation: re-found the RPB2 marker (3389 bp) by streaming real Logan ERR15383529 unitigs in 11.6 s at 100% identity; offline fixture tests for both aligners; 23 unit/integration tests (parsers, aggregation, resolution, end-to-end) all pass, full suite green.
- BioProject expansion uses the ENA filereport API (`result=read_run&fields=run_accession`); no API key; works for PRJEB and most PRJNA.
- Alternatives considered: (a) Snakemake rules with checkpoints for dynamic accessions — more machinery than the MVP needs; deferred. (b) bait-then-compare (discovery engine) for targeted queries — rejected per D05; less sensitive/specific and would download/index the dataset. (c) single aligner now — premature before calibration; shipping both keeps the rDNA and genome paths both usable.
- Status: Accepted. MVP complete for Logan + local; SRA streaming path needs live validation; minimap2 preset and final aligner choice provisional pending Phase 1.5 calibration.

### 2026-06-19 — D28: Low-abundance endophyte detection from Logan — gate low, confirm by reverse-classification
- Context: first real targeted-search application — scanned 10 Green Biome Institute plant genomes (Logan unitigs) with Harte's *Alternaria* sp. NS26-3-C2 genome as the query, to test whether a fungal endophyte can be detected and distinguished from noise. Full record: `results/alternaria_vs_gbi10/REPORT.md`.
- Outcome: **5/10 plants carry trace, nt-confirmed *Alternaria alternata* (sensu lato)** (Silene 106, Carpenteria 17, Ceanothus 7, Dudleya 5, Carex 2 = 137 hit unitigs; 99–100% identity). Disproves systematic host-filtering of GBI data (foreign fungal DNA survives into Logan).
- Decision 1 — **gate low**: low-abundance endophyte DNA assembles only into short Logan unitigs (~210–470 bp; the genomic echo of the rDNA collapse, D20). The first pass used a ≥500 bp "strict" cut and falsely returned 0/10. Use ≥95% identity over **≥200 bp** for trace genomic recovery, not ≥500.
- Decision 2 — **reverse-classification is mandatory**: confirm every hit by BLAST vs nt. It (a) proves the hit is fungal (a plant ortholog cannot reach 99% over 200 bp), and (b) separates "our genus" from related fungi that cross-match conserved (mito/rRNA) regions of the query genome — 2/15 sampled hits were other Dothideomycetes (*Sclerophomella*, *Zeloasperisporium*).
- Decision 3 — **conserved single-copy DNA marker panels are NOT a usable "any-fungus" probe for Logan unitigs**: intron-laden markers break cross-genus DNA alignment (Alternaria RPB2 could not hit Cladosporium RPB2 in the panel), single-copy markers do not assemble at low abundance, and default `blastn` is megablast (insensitive). The panel returned false zeros and was dropped. A genuine "any-fungus" check needs k-mer containment vs a fungal genome DB (on the saved signatures) or the SRA-reads path.
- Decision 4 — the **whole-genome query is the right probe**: 33 Mb of target gives many chances for a short low-abundance unitig to land somewhere; markers do not.
- Process lesson: an implausibly uniform negative (0/10) is a red flag — never trust a bare zero without a validated positive control. Skepticism, not the first automated number, produced the correct result.
- Status: Accepted. Open: resolve the 5 *Alternaria*-negative plants for "any fungi at all" (saved sourmash sigs vs fungal DB, or SRA-reads path) before calling them fungus-free.
