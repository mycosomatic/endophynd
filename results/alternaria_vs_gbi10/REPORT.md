# Trace *Alternaria* endophyte detection across 10 Green Biome Institute plant genomes

*Endophynd targeted-search analysis. Run 2026-06-19. Author: Claude Code + Harte.*
*Result directory: `results/alternaria_vs_gbi10/`. Tied to git commit (see provenance).*

---

## 1. Question

Take Harte's cultured fungal isolate — *Alternaria* sp. **NS26-3-C2** (assembled
genome, 33.35 Mb, 83 contigs) — and ask, for each of 10 plant genomes: **does this
organism (or its close relatives) occur in that plant's sequencing data, and can we
tell real signal from noise (plant orthologs, other fungi, decontamination
artifacts)?**

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
   │ RESULT: 5/10 plants carry trace, nt-confirmed │
   │ Alternaria alternata (sensu lato) endophyte    │
   └──────────────────────────────────────────────┘
```

**Why `tee` + two consumers:** one S3 download feeds both the aligner (where/how
similar) and the k-mer sketch (how much of the genome is present, ortholog-robust)
— halving bandwidth. FIFOs guarantee both finish before the stream is discarded.

---

## 4. Result

**5 of 10 plants carry trace *Alternaria*; 5 do not** (at the corrected threshold,
≥95% identity over ≥200 bp, each hit confirmed by BLAST vs NCBI nt):

| Plant | hit unitigs | of which *Alternaria* | other fungi | median id | longest aln |
|---|---|---|---|---|---|
| *Silene verecunda* | 106 | 88 | 18 | 99.2% | 466 bp |
| *Carpenteria californica* | 17 | 17 | 0 | 100% | 262 bp |
| *Ceanothus ophiochilus* | 7 | 6 | 1 | 99.5% | 269 bp |
| *Dudleya viscida* | 5 | 5 | 0 | 99.5% | 258 bp |
| *Carex obispoensis* | 2 | 2 | 0 | 98.8% | 296 bp |
| *Streptanthus, Iris, Berberis, Rosa, Calochortus* | 0 | 0 | 0 | — | — |

Total: **137 hits, and every one is fungal — zero plant/bacterial false positives.**
nt reverse-classification: **118 *Alternaria*** (the *alternata* species complex —
*brassicae/alternata/arborescens/tenuissima*, indistinguishable, see §6) and **19
other fungi** (16 environmental "Fungal sp." plus *Stemphylium*, *Bipolaris*,
*Sclerophomella* — Dothideomycetes matched through conserved mitochondrial/rRNA
regions of the query). Per-hit detail with our-genome *and* nt identities:
`hits/confirmed_hits.tsv`; per-plant FASTAs to re-BLAST by hand:
`hits/per_plant/<species>.alternaria_hits.fa`.

That 100%-fungal specificity (no plant orthologs sneaking through at ≥95% / ≥200 bp)
is the headline validation of the corrected method.

**Interpretation.** *Alternaria alternata* sensu lato — a cosmopolitan plant-
associated fungus — is present as a **low-abundance endophyte/contaminant** in half
of these unrelated California plant genomes. "Low-abundance" is why the unitigs are
short (~210–470 bp): there is too little endophyte DNA for Logan to assemble past
the conserved/unique boundaries (the genomic echo of the rDNA collapse in D20). The
signal is nonetheless unambiguous — 99–100% identity over 200+ bp is far outside
what a plant ortholog could produce, and nt BLAST independently calls it fungal.

**On decontamination (the key worry).** The presence of foreign fungal DNA in 5/10
datasets **disproves systematic host-filtering** of these GBI submissions — the
endophyte signal survives all the way into Logan. So the strategy works; the 5
zeros most likely reflect genuine absence of *Alternaria* specifically (a distant
fungus would not match the *Alternaria* genome at all — see §6, open items).

---

## 5. What went wrong first, and how it was caught

The first automated pass reported **0/10 — "no fungal signal, inconclusive."** That
was wrong, and only skepticism about an implausibly uniform zero exposed it. Two
bugs:

1. **Threshold too strict.** "Real hit" was set at ≥500 bp. But a low-abundance
   endophyte only assembles into ~250 bp Logan unitigs, so the genuine signal sat
   *just under* the cut and was silently discarded. **Fix:** ≥200 bp, then confirm
   each hit by reverse-classification. Lowering the bar surfaced all 137 hits.
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

- **Species resolution.** Hits are 96–100% to *A. alternata* / *A. brassicae*. The
  *A. alternata* complex is barely resolvable even with genomes, so the honest call
  is "*Alternaria* sect. *Alternaria*, indistinguishable from NS26-3-C2 at this
  resolution," not a named strain.
- **Specificity.** 2/15 sampled hits were non-*Alternaria* Dothideomycetes caught
  through conserved regions of the *Alternaria* genome query. Raw ALT counts
  therefore slightly over-read *Alternaria*-specific signal; the
  `confirmed_hits.tsv` nt column is the arbiter.
- **The 5 zeros are "no *Alternaria*," not "no fungi."** A distant fungus (e.g. a
  Basidiomycete) would not match the *Alternaria* genome at all. A proper
  "any-fungus" check needs either the saved sourmash signatures vs a fungal genome
  DB, or the SRA-reads path. *Not yet done.*
- **Sensitivity floor.** Logan drops the lowest-abundance content; the SRA-reads
  path is the sensitive backup for anything marginal.

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
- `SUMMARY.tsv` — per-plant summary (note: the `ALT_strict_hits`/`FUNGAL` columns use
  the *pre-correction* logic; §4 and `hits/` carry the corrected result).
- `hits/all_alt_hits.fa`, `hits/all_alt_hits.meta.tsv` — the 137 unitigs + alignment metadata.
- `hits/all_alt_hits.nt_blast.tsv` — raw nt BLAST output.
- `hits/confirmed_hits.tsv` — merged: alignment + nt classification per unitig (the hand-check table).
- `hits/per_plant/<species>.alternaria_hits.fa` — per-plant annotated FASTAs.
- `per_plant/<acc>.sam`, `<acc>.sig` — raw alignment + k-mer signature per plant (reusable).
- `refs/` — combined reference, index, query/control signatures.
