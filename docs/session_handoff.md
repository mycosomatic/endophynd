# Session Handoff — Logan Unitig Discovery

*Append-only record. Last updated: 2026-06-16. Each session appends a new section.*

---

## Session 2026-06-15: ITSx → BLAST, gate thresholds, seed build

### 1. Logan unitigs in rDNA regions are ~33 bp (k-mer floor)

**Finding**: `ERR15383529` (Alternaria alternata, PE150 Illumina) has rDNA-baited
unitigs with median=33 bp, max=70 bp (n=226,490).

**Why**: Logan uses a k=31 de Bruijn graph. The rDNA operon is tandemly repeated
(50–200 copies) with slight inter-copy variants. Almost every position in ITS1/ITS2
has a branch in the de Bruijn graph → assembler stops → unitig = one or two k-mers.

**Action**: Switch classify rule from q2-feature-classifier to Kraken2 or minimap2
in Phase 2. Deferred; document the blocker here.

### 2. ITSx → BLAST swap was the right call

**Finding**: ITSx detected 0 sequences from 226K Alternaria unitigs. BLAST detected
5,186 (558 coarse + 4,628 discard). ITSx requires SSU/LSU flanks — Logan unitigs
have none.

**Current state**: `scripts/assign_locus_blast.py` + `resources/rdna_ref.fa`
(78 sequences: 28 SSU, 40 ITS, 10 LSU).

### 3. Gate thresholds lowered for unitig reality (D18)

ITS fine=50 bp, SSU/LSU fine=60 bp. Provisional until Phase 1.5 calibration.

### 4. bbduk `minlength=50` may not filter FASTA stdin

Action next session: verify and add explicit post-bait filter if needed.

### 5. q2-feature-classifier is wrong for 33 bp unitigs

**Candidates**: Kraken2 (k-mer, short-read native), minimap2, VSEARCH. Phase 2 task.

---

## Session 2026-06-16: Seed contamination, rDNA assembly root cause, SRA path

### 1. Seed file had 15 mRNA contaminants (FIXED — D19a)

**Finding**: 15 of 99 seeds in `resources/rrna_seeds.fa` were mRNAs for 18S rRNA
processing enzymes (methyltransferases, pseudouridine synthases, maturation proteins,
biogenesis factors — all `XM_` or `NM_` NCBI prefixes). They appeared in the NCBI
title query because their gene names contain "18S rRNA". They caused false-positive
baiting: the most egregious produced a 975 bp methyltransferase CDS hit presented as
rDNA.

**Fix applied**: Added `is_rdna(header)` function to `scripts/build_rrna_seeds.py`
that rejects `XM_`/`NM_` accession prefixes and headers containing enzyme-keyword
terms (methyltransferase, pseudouridine, kinase, etc.). Cleaned seed file from
99 → 84 sequences. Provenance updated.

**Important**: The seed file was ALSO built from an older version of the script
(had `5.8S_Ascomycota`/`5.8S_Basidiomycota` groups that fetched 0 sequences).
The current script has the correct groups (`ITS_Ascomycota`, `ITS_Basidiomycota`,
`ITS_Pleosporales`). When you have NCBI access, rebuild seeds:
```bash
python scripts/build_rrna_seeds.py --email harte.singer@gmail.com
```

### 2. ERR15383529 is confirmed Alternaria alternata WGS PE150 (NOT amplicon)

**Confirmed by ENA metadata**: PRJEB93827 "WGS of Alternaria alternata from wild
tomato", Illumina, strategy=WGS, source=GENOMIC, PAIRED, L=151. 4.7M read pairs,
1.4G bases, 42× genome coverage of a ~33Mb genome.

**BLAST confirmation**: SRA BLAST of a 568bp ITS sequence against ERR15383529 raw
reads gives 100+ hits at 100% identity, 27% query coverage (= ~151bp per read).
The user noted "it's all 5.8S in this search" — the reads landing at 100% identity
are from the conserved 5.8S region; ITS1/ITS2 reads exist but at lower identity
because of isolate-to-reference variation in the variable regions.

### 3. Complete Logan file analysis: max rDNA unitig = 65bp (DEFINITIVE)

**Method**: Downloaded the complete compressed Logan file for ERR15383529 (19.3MB
compressed, 72MB decompressed). This IS the entire file — no partial sampling.
Analyzed all 388,522 unitigs.

**Result with clean seeds (k=31 exact)**:
- Total baited: 1,902 / 388,522
- Max length: 285bp (SSU 18S fragment, only 1 seed k-mer match — possibly
  coincidental)
- ITS junction max: 65bp
- 1,873 sequences are 31bp (single k-mer matches, noise)

**What the 61-65bp hits actually are**: These are the conserved primer-flanking
bases at the ITS4 (ITS2→28S junction) and ITS3 (interior of ITS2) primer sites.
Confirmed by primer sequence matching:
- `ERR15383529_283340`: contains ITS3 primer → real ITS2 sequence, 61bp
- `ERR15383529_302300`: contains ITS4 primer and LSU start → real ITS2→28S, 61bp
- `ERR15383529_340004`: contains 18S→ITS1 junction → real, 61bp
(These are saved in `tests/fixtures/ERR15383529_baited_logan.fa`)

### 4. Root cause confirmed: tandem repeat assembly collapse (D20)

**Control experiment**: Searched same 388K unitigs with published phylogenetic marker
primer sequences (k=17 probe):

| Marker | Max unitig | Notes |
|--------|------------|-------|
| RPB2   | **3,389bp** | Long contig, single-copy gene ✓ |
| RPB1   | **1,991bp** | Long contig, single-copy gene ✓ |
| TEF1a  | **483bp**   | Assembled, single-copy gene ✓ |
| ITS    | **65bp**    | Tandem repeat collapse ✗ |

**Conclusion**: Logan assembly works correctly. The failure is 100% specific to the
rDNA tandem repeat array. The fungal rDNA operon has 10–80 identical copies in
tandem (~7kb each). PE150 reads cannot span repeat unit boundaries. k-mers from all
identical copies collapse to the same node in the de Bruijn graph, forming
unresolvable cyclic paths. Minia can only produce 65bp tip unitigs at the
conserved/unique boundary (primer flanking sites).

**This means Logan IS useful for**:
- Finding Alternaria in a plant genome (TEF1a, RPB2, RPB1 bait cleanly)
- WGS accessions where you want single-copy locus recovery
- Any non-tandem-repeat marker
- The planned "scan many plant genomes with a whole fungal genome query" approach

**Sequences saved**: `tests/fixtures/ERR15383529_protein_coding_control.fa`
(RPB2 3389bp, RPB1 1991bp, TEF1a 483bp). BLAST these locally to confirm identity.

### 5. Samplesheet updated

`ERR15383529` reclassified from `source=logan` to `source=sra` with a note
explaining why. The Logan path for this accession gives only 65bp rDNA fragments.

### 6. A note on the k=15 false positives

When searching with k=15 (very short k-mer), the Alternaria seed sequences appeared
to match long unitigs (2287bp, 2274bp, etc.) but these had 0 matches at k=21 and
were confirmed as non-rDNA (genomic protein-coding sequence). 15-mers are too short
for specific baiting of rDNA; k=31 with hdist=1 (the bbduk default) is appropriate.

---

## Session 2026-06-19: Targeted search MVP (capability B, Phase 4) built

Built `endophynd target` — the "point a query at a group of genomes and find the
Logan unitigs / SRA reads that match" feature (D21).

### What landed
- New package `endophynd/target/`: `models.py`, `resolve.py`, `query.py`,
  `align.py`, `aggregate.py`, `run.py`. New CLI subcommand `endophynd target`.
- **Reference inversion (D05)**: the query is the reference; each target streams
  through it; no dataset-side DB is built or downloaded.
- **Targets**: run accessions (SRR/ERR/DRR), a BioProject (PRJNA/PRJEB →
  expanded via ENA filereport API), local FASTAs, or `@file`. Comma/repeat OK.
- **Sources**: `logan` (built + validated), `local` (built + validated), `sra`
  (command built via `fasterq-dump --stdout`, **not yet live-tested**), `auto`.
- **Aligners**: minimap2 (genome/marker, default) and blastn (rDNA/divergent),
  auto-selected by query type. blastn uses `qseq` to emit matched sequences.
- **D20 caveat is in-tool**: an rDNA query auto-detected against `--source logan`
  prints a warning to switch to SRA (Logan collapses rDNA to ~65 bp).
- **Outputs** (per `--out`): `targeted_summary.tsv` (reverse-lookup headline),
  `targeted_hits.tsv`, `presence_matrix.tsv`, `per_target/<acc>.hits.fa`,
  `provenance.json`.
- Config: `target:` block in `params.yml`; new env `envs/targeted.yml`.
- Docs: guides `10_targeted_search.md` and `02_resolving_accessions.md`.
- Tests: `tests/test_target.py` (23 tests — parsers, aggregation, resolution,
  end-to-end). Full suite: 61 passed.

### Validation done
- REAL Logan stream: RPB2 query vs Logan `ERR15383529` unitigs → re-found the
  3389 bp RPB2 unitig at 100% identity in ~12 s.
- Offline: both aligners find RPB2 in the protein-coding control fixture.
- rDNA auto-detection: 852 bp Aspergillus ITS query → typed `rdna`, aligner
  `blastn`, D20 warning fired.
- Genome-scale real test: Harte's *Alternaria* isolate NS26-3-C2 (33.3 Mb, 83
  contigs) → Logan `ERR15383529` unitigs = **22,331 unitig hits, median 99.5 %
  identity, 31 contigs**, in ~10 s.

### Data-record correction (D22) — surfaced by the genome-scale test
The genome test above exposed a fabrication: **D19 claimed ERR15383529 was an
"ITS amplicon of a Collinsia plant" — false.** ENA confirms it is WGS / GENOMIC
*Alternaria alternata* (isolate CS330, study PRJEB93827). Corrected
non-destructively: D19 banner + status updated (original text preserved), new
**D22** records the verified facts, and `samplesheet.csv` note fixed. *Collinsia
sparsiflora* is the host **flower** Harte isolated fungal endophytes from — not
this external reference accession. Lesson logged: verify accession identity
against ENA/NCBI before recording it.

### Immediate next steps for targeted search
1. **Live-test the SRA path**: `endophynd target -q <ITS.fa> -t ERR15383529
   --source sra --query-type rdna --aligner blastn -o results/its_sra`. Confirm
   `fasterq-dump --stdout --split-spot | awk(fq2fa) | blastn` streams cleanly and
   returns ITS hits. Watch for fasterq-dump stdout reliability (handoff §Option B
   fallback below applies if it stalls).
2. Consider a small real BioProject end-to-end (e.g. a handful of runs) to
   exercise ENA expansion + parallel streaming.
3. minimap2 preset (`asm20`) and the final single-aligner choice are provisional
   pending Phase 1.5 mock-community calibration (§12).
4. Optional: a Snakemake wrapper for resumable large-project runs (deferred; the
   CLI engine already skips nothing and reruns are cheap for Logan).

---

## What to build next: SRA raw-read streaming path (Phase 3, now elevated)

### Why this is urgent

For WGS accessions, raw PE150 reads individually span 150bp of ITS sequence. A read
starting in the 18S/5.8S conserved region will extend 150bp into ITS1/ITS2. A
bbduk-baited PE150 read is therefore a usable ITS fragment for classification,
even without merging. Merged pairs (fastp/BBMerge) give 200-300bp of ITS.

### Implementation plan for `rule retrieve_and_bait` (source=sra)

The rule already handles `source=local` and `source=logan`. Add `source=sra`:

```python
# workflow/config/samplesheet.csv new fields (already schema-compatible):
# source=sra, input_type=reads
```

**Shell command** (streaming, no whole-file disk landing):

```bash
# Option A: fasterq-dump (in retrieve_bait.yml conda env, sra-tools>=3.0)
# Writes interleaved PE to stdout, pipes directly to bbduk
fasterq-dump \
    --stdout \
    --split-spot \          # interleave R1/R2
    --threads {threads} \
    {params.acc} \
| bbduk.sh \
    in=stdin.fastq \
    interleaved=t \         # bbduk understands interleaved PE
    ref={params.seed_ref} \
    outm={output.baited} \
    stats={output.bait_stats} \
    k={params.k} \
    hdist={params.hdist} \
    minlength=100 \         # raw reads: use 100bp, not 50bp
    threads={threads} \
    2>> {log}
```

**Option B (if fasterq-dump streaming is unreliable)**: temp files, merged:

```bash
# Write PE to temp, merge, bait
TMPDIR=$(mktemp -d)
fasterq-dump --split-files --outdir $TMPDIR --threads {threads} {params.acc}
bbmerge.sh \
    in1=$TMPDIR/{params.acc}_1.fastq \
    in2=$TMPDIR/{params.acc}_2.fastq \
    out=$TMPDIR/merged.fq \
    outu=$TMPDIR/unmerged.fq \
    threads={threads}
cat $TMPDIR/merged.fq $TMPDIR/unmerged.fq | \
bbduk.sh in=stdin.fastq ref={params.seed_ref} outm={output.baited} ...
rm -rf $TMPDIR
```

**Recommended approach**: Option A (fasterq-dump --stdout --split-spot) because:
- No disk footprint for a 42× WGS run (~5GB raw fastq)
- Direct pipe to bbduk
- fasterq-dump ≥3.0 supports true stdout streaming

**minlength for raw reads**: Use 100bp (not 50bp used for Logan unitigs). A 100bp
raw read is much more informative than a 50bp unitig and worth keeping.

**After baiting**: The downstream steps (annotate_and_gate, dereplicate, classify)
work on the baited.fa output — no changes needed there. The 100-150bp baited reads
will pass the ITS fine threshold (50bp) easily and get classified properly.

### Conda env change needed

`envs/retrieve_bait.yml` already has `sra-tools>=3.0` — no change needed.
fasterq-dump is in that package.

### Test accession

Use `ERR15383529` (already in samplesheet as `source=sra`). Expected results:
- Baited reads: hundreds to thousands (42× WGS, rDNA ~1% of genome)
- Length distribution: peak at 100-151bp
- BLAST these against UNITE/SILVA to confirm fungal ITS identity
- Many reads will span ITS1, 5.8S, ITS2 independently

### Samplesheet entry (already updated)

```csv
ERR15383529,sra,ERR15383529,illumina,reads,...
```

---

## Open questions (updated)

1. **Why does the conserved 5.8S not produce longer Logan unitigs?** The 5.8S
   (~155bp) is nearly identical across all rDNA copies. At k=31, the 5.8S body
   should form a single long unitig (155bp). We see only 65bp there. Possible
   explanation: Logan uses k=63 (not k=31) → minimum unitig = 64bp, and the 5.8S→ITS
   junctions still collapse at k=63 because even 1-2bp of inter-copy variation in
   the first/last 63bp of 5.8S is enough to create a branch. Worth investigating
   with the full Alternaria alternata reference 5.8S sequence.

2. **What fraction of the 1,902 baited Logan unitigs are genuine vs noise?** The
   1,873 single k-mer (31bp) hits are mostly noise. The 29 hits >50bp are genuine
   (primer-confirmed). The 285bp hit is uncertain (1 seed k-mer match). With clean
   seeds + bbduk hdist=1, real recall from Logan WGS rDNA is ~29 useful sequences.

3. **Will the "whole fungal genome as query" approach for plant genomes work?**
   The user believes this is feasible and has ideas for it. This is the long-term
   Logan-based discovery mode. Protein-coding gene recovery (RPB2 3389bp, etc.)
   strongly supports it — those unitigs are exactly the kind of thing you'd find
   when scanning a plant genome Logan file for fungal contamination/endophytes.

4. **How to handle SRA accessions with very large raw data?** The fasterq-dump
   approach streams data without landing full files. But 42× WGS of a 33Mb genome
   = ~1.4GB of reads streaming through the pipe. bbduk is fast enough. The hot
   cache only receives the tiny baited output (~1-10MB). This is within budget.

---

## Files changed this session (2026-06-16)

| File | Change |
|------|--------|
| `resources/rrna_seeds.fa` | Removed 15 mRNA contaminants; 99 → 84 sequences |
| `resources/rrna_seeds_provenance.yml` | Updated with cleaning record |
| `scripts/build_rrna_seeds.py` | Added `is_rdna()` filter; added `_MRNA_KEYWORDS` regex |
| `workflow/config/samplesheet.csv` | ERR15383529: source=logan → source=sra with notes |
| `docs/decisions.md` | Added D19 (seed contamination + ERR15383529 reclassification) and D20 (tandem repeat control experiment) |
| `tests/fixtures/ERR15383529_baited_logan.fa` | Complete rDNA signal from Logan ERR15383529 (29 sequences >50bp) |
| `tests/fixtures/ERR15383529_protein_coding_control.fa` | RPB2/RPB1/TEF1a unitigs from Logan ERR15383529 |

---

## Git state

Branch: `claude/vigilant-maxwell-vdc9wd`
Last commit: `5836320` — "Add protein-coding control; confirm Logan rDNA failure is
tandem-repeat collapse"
All changes committed and pushed.

## How to start the next session

Tell Claude Code:
> "We're building the SRA raw-read streaming path for endophynd. Read
> `docs/session_handoff.md` for context. The task is to add `source=sra` handling
> to `rule retrieve_and_bait` in `workflow/Snakefile`, using `fasterq-dump
> --stdout --split-spot` piped to `bbduk.sh` with `minlength=100`. Test accession
> is `ERR15383529` (42× Alternaria alternata WGS PE151, already in samplesheet).
> The conda env already has `sra-tools>=3.0`. See the implementation plan in
> `docs/session_handoff.md` under 'What to build next'."
