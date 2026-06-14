# Test Fixtures

Tiny synthetic data for Phase 0 smoke tests. Nothing here is biologically
authentic enough for classification benchmarking — that's in `benchmarks/`.

## Files

- `mock_its_reads.fa` — 5 synthetic reads simulating an ITS/SSU-baited
  output from a plant sample with sparse endophyte signal. Sequences are
  plausible in structure but are NOT real sequencing reads. Reads 1–3
  contain ITS1/ITS2/SSU-like regions; read 4 is plant background; read 5
  is an ITS1 partial.

## What these are for

- Smoke tests: does the pipeline run end-to-end without crashing?
- Schema tests: are output files well-formed?
- Phase 1 will replace these with a few real GBI unitig fragments
  (a handful of sequences, not whole-accession files).
