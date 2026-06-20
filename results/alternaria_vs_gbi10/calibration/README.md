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

## Stress test — how low can the length threshold go? (`leak_frontier.tsv`)

To find the breaking point, 3 datasets (Silene = fungally rich, Streptanthus = clean,
Carpenteria = has the yeast) were re-aligned with a low minimap2 floor (`-s 50`, so
sub-200 bp alignments are reported) and swept across length × identity. Per-class
hit totals at ≥95% identity:

| ≥95% id | L≥50 | L≥75 | L≥100 | L≥125 | L≥150 | L≥200 |
|---|---|---|---|---|---|---|
| **ALT** (signal) | 4902 | 4228 | 3780 | 3432 | 2645 | 140 |
| NPSI (*Psilocybe*, far) | **1510** | 11 | 2 | 0 | 0 | 0 |
| NBOL (*Boletus*, far) | **433** | 7 | 1 | 0 | 0 | 0 |
| NMOR (*Morchella*, near asco) | 10 | 0 | 0 | 0 | 0 | 0 |
| SHUF (pure chance) | **0** | 0 | 0 | 0 | 0 | 0 |
| NSAC (*real* yeast) | 135 | 13 | 10 | 9 | 6 | 4 |

Read-off:

- **Pure chance never leaks.** `SHUF` = 0 in *every* cell, down to ≥50 bp and ≥80%
  identity. Random sequence does not align at these thresholds at any length.
- **It breaks at ~50 bp** — the distant nulls explode (Psilocybe 1510, Boletus 433).
  These are short simple-repeat / low-complexity tracts shared by *all* genomes; even
  ≥99% identity can't rescue 50 bp (those repeats are ≥99% identical everywhere).
- **It's clean again by ~100–125 bp**: at ≥95%/≥100 bp the distant-fungus floor is
  1–2; at **≥125 bp it is exactly 0** — while recovering **~25× more signal** than the
  ultra-conservative ≥200 bp (3,432 vs 140).
- `NSAC` (yeast) persists to ≥200 bp, tracking like signal, not noise — reconfirming
  it is real yeast, not a false floor.

**Conclusions.** The leak is **length-driven low-complexity/repeat cross-talk, not
chance or homology.** Safe operating envelope: **≥95% identity, ≥100–125 bp** (floor
≤2 / 0); the break is at **~50–75 bp**. The shipped ≥200 bp is very conservative —
there is real headroom. **Next upgrade:** because the leak is repeats, masking
low-complexity / simple-repeat regions (DUST on the query, or dropping repeat-class
hits) should push the usable floor well below 100 bp without admitting noise.
(3-dataset probe with `-s 50`; numbers are not directly comparable to the ≥200 bp
calibration run, which used the default `asm20` floor — the *frontier shape* is the point.)

## Files
- `fpr_sweep.tsv` — hits per class across an identity × length grid at the ≥200 bp floor (the FP curve).
- `operating_point.tsv` — per-dataset hits per class at ≥95% / ≥200 bp.
- `null_hits.fa` — the 4 real-genome-null hit sequences (all confirmed *S. cerevisiae*).
- `leak_frontier.tsv` — the dense low-floor stress sweep (`scripts/stress_sweep.py`).
