# Detecting *Alternaria*-query DNA in 10 Green Biome Institute plant sequencing datasets

*Endophynd targeted-search analysis. Run 2026-06-19. Author: Claude Code + Harte.*
*Result directory: `results/alternaria_vs_gbi10/`.*

> ## Scope — what this analysis does and does NOT claim
> **Claims:** which of these plant sequencing **datasets contain DNA** matching the
> *Alternaria* query, and which **fungal DNA** is present in their reads.
> **Does NOT claim:** that any organism *lives in or on* the plant. A hit means the
> DNA was in the reads — **endophyte, leaf-surface contaminant, lab/kit contaminant,
> and Illumina index-hopping are all unexcluded explanations**, and this tool cannot
> separate them. It is a hypothesis generator for follow-up wet-lab work, not proof
> of residency. Its value comes from **scale and replication**, and especially from
> **patterns in rarer, less contaminant-prone taxa** — a cosmopolitan contaminant
> like *Alternaria alternata* is the *weakest* possible signal. This run is a
> 10-dataset pilot.

---

## 1. Question

Take Harte's cultured fungal isolate — *Alternaria* sp. **NS26-3-C2** (assembled
genome, 33.35 Mb, 83 contigs) — and ask, for each of 10 plant sequencing datasets:
**do the reads contain DNA matching this query, can we separate real matches from
artifacts (plant orthologs, conserved-region cross-matches), and which fungal DNA
shows up?** The question is about *DNA in the reads*, not organisms in the plant
(see Scope).

This is the *targeted / reference-inversion* mode (capability B, decision D05): the
query is the reference; each plant dataset is streamed *through* it; only matches
are kept.

---

## 2. Data

**Query (what we look FOR)**
- `NS26-3-C2_final_EGAP_assembly.fasta` — *Alternaria* sp. NS26-3-C2, 33,349,952 bp, 83 contigs (labelled `ALT_` in the combined reference).

**Distant-fungus control (noise floor)**
- *Saccharomyces cerevisiae* R64 (`GCF_000146045.2`), 12.16 Mb, 17 contigs (labelled `CTRL_`). A fungus phylogenetically far from *Alternaria*; if it lights up where *Alternaria* does, the hits are non-specific.

**Targets (what we look IN)** — 10 plant genomes from the **Green Biome Institute**
(NCBI BioProject search `green biome institute`; California native plants). All are
deep Illumina WGS (60–105 Gbp) present in Logan. Diverse families (eudicots +
monocots) chosen for a real specificity spread.

| Run | Species | Family | Logan unitigs (compressed) |
|---|---|---|---|
| SRR30183952 | *Silene verecunda* | Caryophyllaceae | 3.7 GB |
| SRR30183458 | *Streptanthus glandulosus* | Brassicaceae | 0.9 GB |
| SRR35806671 | *Carpenteria californica* | Hydrangeaceae | 1.9 GB |
| SRR35807865 | *Dudleya viscida* | Crassulaceae | 1.6 GB |
| SRR35806735 | *Iris munzii* | Iridaceae (monocot) | 8.9 GB |
| SRR35806654 | *Carex obispoensis* | Cyperaceae (monocot) | 1.5 GB |
| SRR35806652 | *Berberis harrisoniana* | Berberidaceae | 4.6 GB |
| SRR35807883 | *Rosa pinetorum* | Rosaceae | 2.3 GB |
| SRR35806807 | *Ceanothus ophiochilus* | Rhamnaceae | 1.3 GB |
| SRR35806662 | *Calochortus raichei* | Liliaceae (monocot) | 4.0 GB |

Total streamed ≈ **30 GB compressed** (~100 GB after decompression). Nothing whole
was ever landed on disk — only matched unitigs + a tiny k-mer signature per plant.

---

## 3. Data flow (schematic)

```
                       ┌───────────────────────────────────────────────────┐
                       │ COMBINED REFERENCE  (the query; indexed once)       │
                       │   ALT_    = Alternaria NS26-3-C2 genome (33 Mb)      │
                       │   CTRL_   = S. cerevisiae R64 (distant-fungus floor) │
                       │   FUNGAL_ = conserved-marker panel  ✗ DROPPED (§5)   │
                       └─────────────────────────┬─────────────────────────┘
                                                 │ combined_ref.fa
  10 plant Logan accessions                      ▼
  (Illumina WGS, 0.9–8.9 GB)        ┌──────────────────────────────────────┐
        │                          │  PER PLANT  (×10, 3 in parallel)       │
        ▼                          │                                        │
  s3://logan-pub/u/<acc>/          │  aws s3 cp  (stream; never lands whole)│
  <acc>.unitigs.fa.zst ──stream──▶ │      │ zstdcat                          │
                                   │      ▼                                  │
                                   │     tee ──────┬───────────────┐         │
                                   │               ▼               ▼         │
                                   │      minimap2 -ax asm20   sourmash      │
                                   │      --secondary=no       sketch k=31   │
                                   │               │               │         │
                                   │               ▼               ▼         │
                                   │      samtools -F4         <acc>.sig     │
                                   │               │          (k-mer set)    │
                                   │               ▼               │         │
                                   │          <acc>.sam ───────────┤         │
                                   └───────────────────────────────┼────────┘
                                                                   ▼
                              ┌────────────────────────────────────────────┐
                              │ PER-PLANT PROFILE                           │
                              │   ALT  hits   → is OUR organism here?        │
                              │   CTRL hits   → cross-alignment noise floor  │
                              │   containment → alt/ctrl k-mers vs <acc>.sig │
                              └──────────────────────┬─────────────────────┘
                                                     │
        ┌──────────── CORRECTION (skepticism, §5) ───┘
        │  bug 1: strict ≥500 bp HID short low-abundance unitigs  → relax to ≥200 bp
        │  bug 2: FUNGAL marker panel was BLIND (introns)         → drop it
        ▼
   ┌──────────────────────────────────────────────┐
   │ ALT hits ≥95% identity, ≥200 bp  →  137 total │   extract unitig sequences
   └───────────────────────┬──────────────────────┘
                           ▼
   ┌──────────────────────────────────────────────┐
   │ REVERSE-CLASSIFY each unitig vs NCBI nt        │   ← independent confirmation
   │   (is the best hit Alternaria? another fungus? │     (separates "ours" from
   │    a plant? → only fungal hits are real signal)│      relatives & noise)
   └───────────────────────┬──────────────────────┘
                           ▼
   ┌──────────────────────────────────────────────┐
   │ RESULT: 5/10 datasets contain DNA matching the │
   │ query at single-copy nuclear loci              │
   │ (source undetermined — see Scope)              │
   └──────────────────────────────────────────────┘
```

**Why `tee` + two consumers:** one S3 download feeds both the aligner (where/how
similar) and the k-mer sketch (how much of the genome is present, ortholog-robust)
— halving bandwidth. FIFOs guarantee both finish before the stream is discarded.

**Caveat on the sketch branch:** the sourmash containment step shown above
**produced no usable output** in this run (the `prefetch` parse returned empty for
all 10 datasets — a tooling/format bug, not a biological zero), so containment
contributed *zero* evidence here. The result rests on the alignment + nt
reverse-classification path alone. Containment is retained in the pipeline pending a fix.

---

## 4. Result

**5 of 10 datasets contain DNA matching the *Alternaria* query; 5 do not** (≥95%
identity over ≥200 bp; every retained hit nt-confirmed fungal — no plant/bacterial
hits). After stripping conserved-locus (mitochondrial / rRNA) cross-matches — which
are *not* query-specific (§6) — the **single-copy-nuclear, *Alternaria*-specific**
signal per dataset is:

| Dataset (plant) | nuclear *Alternaria*-specific unitigs | mito/rRNA cross-matches | median id |
|---|---|---|---|
| *Silene verecunda* | 84 | 22 | 99.2% |
| *Carpenteria californica* | 17 | 0 | 100% |
| *Ceanothus ophiochilus* | 6 | 1 | 99.5% |
| *Dudleya viscida* | 5 | 0 | 99.5% |
| *Carex obispoensis* | 2 | 0 | 98.8% |
| *Streptanthus, Iris, Berberis, Rosa, Calochortus* | 0 | 0 | — |

**114 nuclear-specific unitigs + 23 conserved-region cross-matches = 137 total**, all
fungal (136 distinct unitigs; one BLAST record is duplicated). The **same 5 datasets
are positive whether or not the cross-matches are stripped**, so *which datasets carry
the signal* is robust — the cross-matches only inflated counts. The nuclear hits are
*Alternaria* (the *alternata* complex — *brassicae/alternata/arborescens/tenuissima*,
indistinguishable, §6); the 23 stripped hits are *other* Dothideomycetes
(*Stemphylium*, *Bipolaris*, "Fungal sp.") matched through conserved mito/rRNA regions
of the query — a non-specific byproduct, not evidence about *Alternaria*. Per-hit
detail (our-genome + nt identity, hand-checkable): `hits/confirmed_hits.tsv`.

**What this shows — and what it does not.** It shows: *Alternaria* sect. *Alternaria*
DNA, at 99–100% identity to **public references**, is present in the reads of 5/10
datasets, at abundance low enough that Logan assembles only short (~210–470 bp)
fragments — consistent with **low sequencing coverage** of a minor component (this is
*not* the D20 tandem-repeat mechanism; these are single-copy nuclear loci). It does
**not** show the fungus was alive, in the tissue, or even on the plant, and the
100%-to-published-reference pattern is equally consistent with index-hopping or a
query↔reference near-clone — see §6 before reading anything into it.

**Independent corroboration (raw SRA reads).** To check that these hits are not a Logan
*assembly* artifact, one hit unitig (~250 bp) was BLASTed against the **NCBI SRA**
database for its source run. It recovered **~20 raw reads that tile the unitig in an
overlapping coverage pattern** — the reads stagger across the ~250 bp window with
mutual overlap, mirroring how the assembler walked them into a single unitig. This
confirms the matching DNA is present in the **raw reads themselves** (not introduced by
Logan's assembly) and that the locus is covered by **multiple independent, overlapping
reads** rather than one isolated read. Multi-read overlapping coverage is more
consistent with genuine low-coverage DNA than with a single index-hopped read; it does
**not**, however, exclude *deeper* index-hopping (many hopped reads can also tile), so
the source-undetermined caveat (§6) stands unchanged.

---

## 5. What went wrong first, and how it was caught

The first automated pass reported **0/10 — "no fungal signal, inconclusive."** That
was wrong, and only skepticism about an implausibly uniform zero exposed it. Two
bugs:

1. **Threshold too strict — the corrected one began post-hoc but is now calibrated.**
   "Real hit" was first set at ≥500 bp; that gave 0/10. Low-*coverage* DNA assembles
   into only ~210–470 bp Logan unitigs, so the genuine matches sat *just under* the
   cut. Relaxing to ≥200 bp surfaced them — initially post-hoc (**chosen after seeing
   that ≥500 gave zero**). It has **since been calibrated** with biologically-absent
   null genomes + a composition shuffle (`calibration/`, decision D29): at ≥95% /
   ≥200 bp the false-positive floor (distant absent fungi *and* a shuffled query) is
   **0** across all 10 datasets and the ALT signal exceeds it ~34×. (My earlier "echo
   of D20" rationale was wrong: D20 is *tandem-repeat* collapse; these are single-copy
   loci, short purely from *low coverage*.)
2. **The "any-fungus" marker control was blind.** It used a panel of conserved
   single-copy markers (RPB2/TEF1/β-tubulin). Two compounding failures: (a) those
   genes are intron-laden, so cross-genus *DNA* alignment catches only short exon
   scraps — *Alternaria*'s own RPB2 could not even hit *Cladosporium* RPB2 in the
   panel; (b) default `blastn` is megablast (tuned for >95% identity). So `FUNGAL=0`
   meant "detector blind," not "no fungi." **Fix:** panel dropped; nt
   reverse-classification is the working specificity layer.

**Lesson (logged as D28):** for low-abundance recovery from Logan, gate *low* and
*confirm by reverse-classification*; never trust a bare zero without a validated
positive control.

---

## 6. Caveats & open items

- **Source is undetermined — the headline caveat.** A hit is "this DNA was in these
  reads." It does **not** distinguish a living endophyte from a leaf-surface
  contaminant, a lab/kit contaminant, or **Illumina index-hopping** from *Alternaria*
  libraries co-sequenced on the same flowcell. The 100%-identity-to-*published*-
  reference pattern is exactly what index-hopping or a query↔reference near-clone
  would produce. Ruling these out needs flowcell/co-sequencing metadata and a
  per-dataset coverage-coherence check (real signal should *tile* the query genome,
  not scatter as isolated high-identity tips). **"Endophyte" is unsupported; the
  ceiling is "*Alternaria* DNA present, source undetermined."**
- **Where credibility actually comes from: scale + rarer taxa.** *A. alternata* s.l.
  is a cosmopolitan pathogen/contaminant, so its presence is weak evidence of
  anything. The tool earns its keep at **large sample size**, and especially on
  **less common, less contaminant-prone fungi**, where a reproducible *pattern of
  co-occurrence* across many datasets is hard to dismiss. This 10-dataset run is
  hypothesis-generating, not conclusive.
- **Now calibrated with proper nulls** (`calibration/`, D29), replacing the pilot's
  inadequate *S. cerevisiae* control. Yeast is itself a plausible endophyte/contaminant
  (it registered 4 *real* yeast hits at ≥200 bp), so it is not a valid null. The
  calibration added biologically-absent macrofungi (*Morchella/Boletus/Psilocybe*) +
  a shuffle and measured a **0** false-positive floor at ≥95% / ≥200 bp (above).
  *Caveat:* that floor is for chance + distant-fungus cross-talk, **not** index-hopping
  (a null cannot be hopped) and **not** for an absent *close* relative of the query.
  Separately, the conserved-marker "any-fungus" panel still failed for tooling reasons,
  so the **5 negatives remain uncharacterized for *other* fungi** ("no *Alternaria*-query
  match," not "no fungi").
- **Threshold is calibrated** (§5, `calibration/`, D29): the ≥95% / ≥200 bp
  false-positive floor — distant absent fungi (*Morchella/Boletus/Psilocybe*) plus a
  composition-shuffled query — is 0 across all 10 datasets; ALT exceeds it ~34×. The
  floor covers chance + distant-fungus cross-talk only (not index-hopping, not an
  absent close relative).
- **Species resolution is section-level.** Top hits span *A. alternata/brassicae/
  arborescens/tenuissima* — i.e. *Alternaria* sect. *Alternaria*, not a species; the
  query is indistinguishable from public complex members at this fragment length.
- **Reproducibility.** Remote nt BLAST with `-max_target_seqs 1` is non-deterministic
  and does not guarantee the best hit (a known BLAST pitfall); species-level calls
  can drift run-to-run. nt confirmation establishes *fungal/phylum*, not residency.
- **On host-filtering.** Foreign fungal DNA surviving into Logan shows these *raw
  reads* were not host-filtered before SRA upload; it says nothing about GBI's
  released *assemblies* (Logan is built from raw reads). Do not over-read it.
- **Sensitivity floor.** Logan drops the lowest-coverage content; the SRA-reads path
  is the sensitive backup for anything marginal.

---

## 7. Reproduce / hand-check

Everything is scripted and re-runnable:

```bash
# 1. references + signatures
#    combined_ref.fa = ALT_ (genome) + CTRL_ (S. cerevisiae) [+ FUNGAL_ panel]
# 2. per-plant stream → minimap2 + sourmash (3 in parallel)
cut -f1 results/alternaria_vs_gbi10/plants10.tsv \
  | xargs -P 3 -I{} bash scripts/scan_one_plant.sh {}
# 3. collect corrected hits + reverse-classify
python3 scripts/collect_alt_hits.py --min-id 0.95 --min-aln 200
blastn -query results/alternaria_vs_gbi10/hits/all_alt_hits.fa -db nt -remote \
  -outfmt '6 qseqid pident length evalue staxids ssciname stitle' -max_target_seqs 1
```

**To hand-check any hit:** open `hits/per_plant/<species>.alternaria_hits.fa`, copy a
sequence, and paste it into NCBI BLAST (web). The header records where it aligned in
the NS26-3-C2 genome and at what identity; `hits/confirmed_hits.tsv` records the nt
top hit. They should agree (fungal / *Alternaria*).

### Files in this directory
- `SUMMARY.tsv` — **corrected** per-plant summary built from `hits/confirmed_hits.tsv`
  (columns: `run`, `species`, `family`, `total_hits`, `nuclear_alternaria_hits`,
  `mito_rRNA_crossmatch_hits`, `median_our_genome_identity`, `call`). The `call` is
  *"query-DNA present (source undetermined)"* for the 5 positives and *"no query match"*
  for the 5 negatives; counts agree with §4.
- `SUMMARY.precorrection.tsv` — the **superseded** pre-correction table (≥500 bp gate +
  blind FUNGAL panel, all 10 "INCONCLUSIVE"); kept for audit (see §5).
- `provenance.json` — git commit, analysis/nt-BLAST date, tool versions, query-genome
  checksum/size, control, params, and the 10 plant accessions.
- `refs/README.md` — how to rebuild `combined_ref.fa` (ALT_ query genome + CTRL_
  *S. cerevisiae* + the dropped FUNGAL_ panel); note `refs/` contents are gitignored.
- `hits/all_alt_hits.fa`, `hits/all_alt_hits.meta.tsv` — 137 hit records (136 distinct unitigs) + alignment metadata.
- `hits/all_alt_hits.nt_blast.tsv` — raw nt BLAST output.
- `hits/confirmed_hits.tsv` — merged: alignment + nt classification per hit (the hand-check table; the authoritative per-hit source for `SUMMARY.tsv`).
- `hits/per_plant/<species>.alternaria_hits.fa` — per-plant annotated FASTAs.
- `per_plant/<acc>.sam`, `<acc>.sig` — raw alignment + k-mer signature per plant (reusable).
- `refs/` — combined reference, index, query/control signatures (gitignored except `refs/README.md`).
