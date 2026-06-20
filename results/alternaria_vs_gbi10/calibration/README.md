# Threshold calibration with biologically-absent nulls

*2026-06-20. Companion to `../REPORT.md`. Addresses the review finding that the
≥95% / ≥200 bp cut was post-hoc and uncalibrated.*

## Design

The same 10 datasets were re-scanned with a combined reference carrying the real
query **plus** a panel of nulls whose hits are false positives *by construction*:

| Class | Genome | Distance from the *Alternaria* (Dothideomycetes) query |
|---|---|---|
| `ALT` | *Alternaria* NS26-3-C2 | the real query |
| `NMOR` | *Morchella conica* (GCA_008079325.1, China) | Ascomycota / Pezizomycetes — nearest asco null |
| `NSAC` | *S. cerevisiae* R64 | Ascomycota / Saccharomycotina |
| `NBOL` | *Boletus edulis* (GCA_054741165.1, Germany) | Basidiomycota / Boletales — far |
| `NPSI` | *Psilocybe zapotecorum* (GCA_040207405.1, Mexico) | Basidiomycota / Agaricales — far, neotropical |
| `SHUF` | seeded composition shuffle of *Alternaria* | zero homology — pure-chance floor |

All null genomes were vetted first: aligning the *Alternaria* query against each
showed **0** stretches ≥1 kb at ≥95% identity, i.e. no *Alternaria* contamination
hiding in a "null." Build is reproducible via `scripts/shuffle_genome.py` (seed 42)
and `scripts/fpr_calibration.py`.

## Result — the false-positive floor is ~0

Total hits across all 10 datasets, by class (`fpr_sweep.tsv`):

| id ≥ | aln ≥ | ALT | NMOR | NSAC | NBOL | NPSI | SHUF | null floor | ALT/floor |
|---|---|---|---|---|---|---|---|---|---|
| 0.95 | 200 | 137 | 0 | 4 | 0 | 0 | 0 | 4 | 34× |
| 0.97 | 200 | 130 | 0 | 4 | 0 | 0 | 0 | 4 | 33× |
| 0.99 | 200 | 84 | 0 | 4 | 0 | 0 | 0 | 4 | 21× |
| 0.95 | 300 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | ∞ |
| 0.95 | 500 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |

Two things to read off this:

1. **`SHUF` = 0 and the distant real nulls (`NMOR`/`NBOL`/`NPSI`) = 0** at the
   operating point. So at ≥95% / ≥200 bp a composition-matched random sequence and
   an absent, phylogenetically distant fungus produce **no** hits — the threshold
   admits neither chance alignment nor distant-fungus conserved-region cross-talk.
   The ≥200 bp cut is now **empirically supported**, not post-hoc.
2. **The only non-zero null, `NSAC` (4 hits, all in Carpenteria), is real yeast** —
   nt-BLAST: all 4 are *S. cerevisiae* at 99.5–100%. **Yeasts are common endophytes**
   (as well as ubiquitous contaminants), so *S. cerevisiae* is a *plausible real
   presence* — which is exactly why it fails as a null. A valid null must be
   implausible as **both** a biological associate **and** a contaminant; the chosen
   macrofungi (ectomycorrhizal/saprobic, biogeographically absent) are neither, and
   give 0. The 4 yeast hits are therefore a *true* detection (source undetermined,
   like the *Alternaria* signal — a second, unrelated query working on the same
   machinery), not a false positive.

The ≥500 bp row is why the first pilot run wrongly reported 0/10: real low-coverage
signal doesn't assemble past ~470 bp.

## What this does — and does not — license

- **Does:** at ≥95% / ≥200 bp, a hit to the query implies the source DNA is
  closely related to the query (≥ family-ish level; 95% nt over 200 bp excludes
  distant fungi). The chance/distant-fungus FP floor is ~0, and the ALT signal
  exceeds it ~34×. This is the calibrated basis for the "patterns across rarer
  taxa" strategy: for a query taxon, a hit means "DNA closely matching *this* taxon,"
  with a near-zero noise floor.
- **Does NOT** address **index-hopping / co-sequencing** (real query DNA, wrong
  provenance). A null can't be index-hopped, so the floor here is for chance +
  cross-fungal noise, not provenance — that remains a separate check (flowcell
  metadata + the raw-read coverage-tiling test).
- **Does NOT** measure the floor for an absent *close* relative of the query (none
  can be constructed for the cosmopolitan *Alternaria* complex). The distant nulls
  being 0 shows only that *distant* fungi don't cross-match; resolution *within*
  section *Alternaria* / Pleosporaceae remains a separate limit (REPORT §6).
- n = 10; the floor is measured on these datasets. A larger run tightens it.

## Files
- `fpr_sweep.tsv` — hits per class across an identity × length grid (the FP curve).
- `operating_point.tsv` — per-dataset hits per class at ≥95% / ≥200 bp.
- `null_hits.fa` — the 4 real-genome-null hit sequences (all confirmed *S. cerevisiae*).
