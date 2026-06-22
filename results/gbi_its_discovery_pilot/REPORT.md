# GBI ITS-discovery pilot — capability A on real plant WGS

**Date:** 2026-06-21  ·  **Branch:** `claude/targeted-search-gbi-scan`
**Status:** pilot (n=2), method validated; see limits below.

## What this is

The first end-to-end run of **capability A (discovery: "what fungi are in here?")**
on real Green Biome Institute plant WGS data. It is the discovery mirror of the
targeted scan in `results/alternaria_vs_gbi10/` (D28): instead of pointing an
*Alternaria* genome at the datasets, we recover **fungal rDNA (ITS) directly from
the raw SRA reads** and classify it against UNITE — blind to what should be there.

Two datasets, chosen as a controlled contrast (one full-depth run each):

| run | host | D28 *Alternaria* (nuclear-DNA) call |
|---|---|---|
| `SRR30183952` | *Silene verecunda* (Caryophyllaceae) | **positive** (strongest: 84 nuclear hits) |
| `SRR30183458` | *Streptanthus glandulosus* (Brassicaceae) | **negative** (0 hits) |

## Method (validated chain)

```
prefetch .sra  →  fastq-dump (stream local .sra)  →  bbduk bait (conserved rDNA
seeds, k=31 hdist=1 minlen=100, int=f threads=4)  →  vsearch derep  →  ITSx
(extract ITS1/ITS2, -t F,T, partial)  →  vsearch derep(relabel)  →
blastn vs UNITE 10.0 (≥90% id, ≥60% qcov)  →  per-genus fungal table
```

**Key method decision — the fungal/non-fungal discriminator is BLAST, not SINTAX.**
Against a Fungi-only reference (UNITE), `vsearch --sintax` assigns *every* query
`k:Fungi` with kingdom-bootstrap 1.0 — including host-plant ITS — because the
nearest reference is always a fungus (deeper ranks then collapse to low bootstrap).
So `k:Fungi` is useless as a filter. The genuine fungi are the sequences that
**blast to UNITE at ≥90% identity over the ITSx-extracted ITS1/ITS2** (the conserved
5.8S is removed by ITSx, so plant ITS cannot spuriously match a fungal ITS).

## Results

| | *Silene* (positive) | *Streptanthus* (negative) |
|---|---|---|
| reads (total) | 230.7 M | 220.0 M |
| baited (rDNA) | 1.20 M | 11.08 M |
| ITSx ITS1 / ITS2 | 20,623 / 1,397 | 85,138 / 6,117 |
| **confident fungal ITS (unique)** | **256** | **619** |
| **Alternaria ITS** | **8 (97–100% id)** | **0** |

Tables: `SUMMARY.tsv`, `genus_table.tsv`, `alternaria_hits.tsv`.

### Headline — the D28 contrast reproduces via an independent path

*Alternaria* ITS is present in *Silene* (4 hits at **100% identity**, incl.
*A. tenuissima* 100%/107 bp) and **absent** in *Streptanthus*. D28 detected
*Alternaria* **nuclear genome** DNA in *Silene* and none in *Streptanthus*. This
run uses a **different molecule (rDNA vs nuclear), different data (SRA reads vs
Logan unitigs), and a different method (discovery vs targeted)** and lands on the
**same call**. A plant ITS cannot hit *A. tenuissima* at 100% over 107 bp, so the
hits are genuinely *Alternaria*. Two orthogonal methods agreeing is the strongest
evidence to date that the *Silene*↔*Alternaria* association is real signal.

## Honest limits

1. **The negative is fungus-rich, not Alternaria-free by failure.** *Streptanthus*
   yielded *more* total fungal ITS (619 vs 256); it simply contains no *Alternaria*.
   So the absence is specific, not a recovery artifact. This strengthens the contrast.

2. **Most recovered "fungi" look like a shared background, not host endophytes.**
   Both unrelated hosts are dominated by the *same* genera — *Hyphopichia*,
   *Derxomyces* (yeasts), *Ceraceosorus*, *Thelephora*, *Scleroderma*, *Boletus*
   (ectomycorrhizal basidios), *Cordyceps*. These are implausible shared endophytes
   of both a Caryophyllaceae and a Brassicaceae; the same-genera-in-both pattern is
   consistent with a **reagent / environmental / index-hop background** common to the
   GBI run. Per D28, source is undetermined. **The biologically meaningful signal is
   the difference between samples (Alternaria), not the shared bulk.** A proper
   discovery analysis at scale needs a background model (genera shared across all
   GBI samples ≈ contamination signature) and ideally a kit/blank control.

3. **Alternaria is low-abundance** (8 unique ITS, all size=1). Index-hopping from a
   co-multiplexed Alternaria-rich sample cannot be fully excluded — but uniform
   index-hopping would also seed the negative, and it did not. The positive/negative
   specificity argues against it; it does not prove residency (endophyte vs surface
   vs lab).

4. **n = 2.** This is a controlled pilot, not the population test. The real
   validation is whether *Alternaria*-ITS presence tracks the D28 5-positive /
   5-negative split across all 10 GBI datasets.

## Reproducibility

Scripts in `scripts/`: `run_gbi2.sh` (recovery), `classify_compare.sh`
(classification), `analyze_fungal.py` / `save_tables.py` (aggregation). Tool
versions, parameters, and the UNITE checksum are in `provenance.json`. Raw reads,
baited FASTAs, and ITSx intermediates are process-then-delete (not retained); the
`.sra` files were streamed and removed.

### Engineering notes (gotchas hit and fixed)
- `fasterq-dump --stdout` direct-from-remote **hangs** (sra-tools 2.11.3) and its
  local mode needs ~193 GB scratch/dataset — switched to `prefetch` + `fastq-dump`
  streaming from the local `.sra` (negligible scratch).
- `bbduk` reading FASTQ from **stdin at threads=16 crashes** ("missing plus" — the
  multithreaded stream reader misaligns records). Use **threads=4** for stdin baiting.
