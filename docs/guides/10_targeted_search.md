# Guide 10 — Targeted search: "which datasets contain this sequence?"

**Purpose.** You have a query — a fungal genome, a single-copy marker (RPB2,
TEF1a…), or an rDNA/ITS barcode — and you want to know which Logan/SRA datasets
contain it, and to pull out the exact unitigs/reads that match. This is
*targeted mode* (capability B). It is the mirror image of discovery: discovery
asks "what's in this plant?", targeted asks "which plants have this taxon?".

**How it works (the one idea).** *Reference inversion* (decision D05): your query
becomes the tiny reference, and each target dataset is **streamed through it** by
alignment. Nothing about the dataset is downloaded or indexed — only the small
matching records are kept. This is what keeps disk and compute tiny even for a
whole BioProject.

---

## Prerequisites

Tools (all in `envs/targeted.yml`): `minimap2`, `blast` (blastn + makeblastdb),
`samtools`, `awscli`, `zstd`, `sra-tools`. The pipeline streams from the public
Logan bucket with `--no-sign-request`, so **no AWS account is needed**.

---

## Quick start

```bash
# Genome / marker query against a single Logan accession
endophynd target \
  --query my_fungus_markers.fa \
  --targets ERR15383529 \
  --source logan \
  --out results/targeted_demo
```

What you get in `results/targeted_demo/`:

| File | What it answers |
|------|-----------------|
| `targeted_summary.tsv` | **The headline.** One row per (query, target) with ≥1 hit: best/mean identity, max alignment length, union query coverage. "Which datasets contain my query, how well." |
| `targeted_hits.tsv` | Every individual hit (long form). |
| `presence_matrix.tsv` | Wide matrix: query rows × target columns, value = number of hits. |
| `per_target/<acc>.hits.fa` | The actual Logan unitigs / SRA reads that matched. |
| `provenance.json` | Query, params, tool versions, git commit, per-target status. |

---

## Specifying targets

`--targets` is repeatable and comma-separated, and accepts:

- **Run accessions:** `--targets ERR15383529,SRR123,DRR456`
- **A BioProject** (expanded to its runs via ENA): `--targets PRJEB93827`
- **A local FASTA** (search a genome you already have): `--targets path/to/genome.fa`
- **A file of any of the above:** `--targets @accessions.txt` (one per line, `#` comments)

See `docs/guides/02_resolving_accessions.md` for BioProject → run expansion.

## Choosing the source (`--source`)

- `auto` (default) — use Logan if the accession is in the bucket, else SRA.
- `logan` — stream Logan unitigs (cheap: 10–100 MB compressed per accession).
- `sra` — stream raw reads with `fasterq-dump` (heavier: GBs per run).
- `local` — read a FASTA/FASTQ already on disk.

> ⚠️ **rDNA queries and Logan don't mix (decision D20).** Logan collapses the
> rDNA tandem array to ~65 bp, so an ITS/LSU/SSU query finds almost nothing in
> Logan unitigs. The tool auto-detects an rDNA query and **warns you** to use
> `--source sra`. Genome and single-copy-marker queries work great against Logan.

## Choosing the aligner (`--aligner`)

`auto` picks **minimap2** for genome/marker queries (fast, near-identity) and
**blastn** for rDNA queries (sensitive to divergence). Override with
`--aligner minimap2|blastn`. The final single-aligner recommendation and the
minimap2 preset are provisional pending mock-community calibration (plan §12).

## Tuning what counts as a hit

| Flag | Default | Meaning |
|------|---------|---------|
| `--min-identity` | 0.80 | drop hits below this identity (0–1) |
| `--min-aln-len` | 50 | drop hits shorter than this (bp) |
| `--min-query-cov` | 0.0 | require this fraction of the query record covered by one hit |
| `--minimap2-preset` | asm20 | minimap2 `-x` preset (allows ~20% divergence) |
| `--jobs` | 4 | parallel targets streamed at once |
| `--threads` | 4 | threads per aligner |

---

## Worked examples

**Scan a whole BioProject for a fungal marker panel:**
```bash
endophynd target \
  --query alternaria_markers.fa \
  --targets PRJEB93827 \
  --source auto --aligner minimap2 \
  --jobs 8 \
  --out results/alternaria_in_PRJEB93827
# Then: sort -t$'\t' -k6 -rn results/.../targeted_summary.tsv | head
```

**Find an ITS barcode across SRA runs (rDNA → must use SRA):**
```bash
endophynd target \
  --query cultured_endophyte_ITS.fa \
  --targets @my_runs.txt \
  --source sra --query-type rdna --aligner blastn \
  --min-identity 0.90 \
  --out results/its_search
```

---

## What success looks like

`provenance.json` shows `n_hits > 0` and `target_status: {"ok": N}`. The matching
sequences are in `per_target/`. On the validation run (RPB2 query vs real Logan
`ERR15383529`), the RPB2 unitig is re-found at 100% identity over 3389 bp in ~12 s.

## Common failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 0 hits, rDNA query, `--source logan` | D20: Logan has only ~65 bp rDNA fragments | use `--source sra` |
| target status `absent` | accession not in Logan bucket | use `--source sra`, or check the accession |
| BioProject expands to 0 runs | wrong accession, or no `read_run` records | verify on ENA; see guide 02 |
| `fasterq-dump` slow / stalls | large WGS run streaming | expected; reduce `--jobs`, or prefer Logan |
| Many weak hits | identity threshold too low | raise `--min-identity` / `--min-aln-len` |
