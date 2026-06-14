# Guide 01: Getting Started

*Goal: install the dev environment, run the Phase 0 scaffold pipeline, and
verify it works on your machine.*

---

## Prerequisites

- Linux or WSL2 (Windows Subsystem for Linux)
- [Miniforge](https://github.com/conda-forge/miniforge) or Miniconda installed
- Git
- ~2 GB free disk space for the base conda environment

---

## 1. Clone the repository

```bash
git clone https://github.com/mycosomatic/endophynd.git
cd endophynd
```

---

## 2. Create the base environment

This installs Python, Snakemake, and the Typer CLI. The heavy bioinformatics
tools (bbduk, ITSx, vsearch, etc.) are in separate per-rule envs that
Snakemake creates automatically when rules run.

```bash
mamba env create -f envs/base.yml
conda activate endophynd
```

Install the Python package in editable mode so the `endophynd` command works:

```bash
pip install -e ".[dev]"
```

Verify:

```bash
endophynd --version
# endophynd 0.1.0
```

---

## 3. Configure cache directories

Open `workflow/config/cache.yml` and set the paths to where you want data to live:

```yaml
hot_dir: "~/endophynd_cache/hot"   # internal SSD
cold_dir: "~/endophynd_cache/cold" # external drive (or any large volume)
db_dir: "~/endophynd_cache/db"     # reference databases
hot_cap_gb: 180                    # hard cap on hot SSD usage
```

**Tip:** If you only have one drive (e.g. during development), you can set
all three to subdirectories of the same location. The important thing is that
`cold_dir` (finished results) never gets deleted by the pipeline.

Verify that the directories are writable:

```bash
endophynd check --config workflow/config/params.yml
```

---

## 4. Run a dry-run

A dry-run shows every rule that *would* run without executing anything:

```bash
snakemake --configfile workflow/config/params.yml --cores 1 --dry-run
```

You should see the rules: `triage`, `retrieve_and_bait`, `annotate_and_gate`,
`dereplicate`, `classify`, `build_feature_table`, `cleanup_transient`, `provenance`.

---

## 5. Run the Phase 0 pipeline on the test fixture

The fixture is a tiny FASTA of synthetic reads in `tests/fixtures/mock_its_reads.fa`.

```bash
snakemake --configfile workflow/config/params.yml --cores 1
```

**What to expect:**
- Rules run sequentially on the single fixture sample (`FIXTURE_ITS`).
- A stub `.qza` file appears under `~/endophynd_cache/cold/results/run_001/FIXTURE_ITS/`.
- A `provenance.json` appears in the same results directory.
- Hot-cache transient files are deleted after classification.

**What Phase 0 does NOT do:** real baiting, real annotation, real classification.
All rules are stubs. The output `.qza` is a placeholder zip, not a valid QIIME2 artifact.

---

## 6. Run the unit tests

```bash
pytest
```

All tests should pass in a few seconds.

---

## 7. Run the first real Logan retrieval (hands-on)

*This step requires `aws` CLI and internet access. It streams a small Logan
unitig file without downloading it — you're just piping a few MB through.*

```bash
# Check that aws CLI is available (no account needed for public Logan data)
aws --version

# Stream a tiny unitig file and look at the first few sequences
aws s3 cp \
  s3://logan-pub/u/GCA_000001405/GCA_000001405.unitigs.fa.zst \
  - --no-sign-request \
  | zstdcat \
  | head -20
```

You should see FASTA headers and sequences streaming to stdout. This is
exactly what the Phase 1 `retrieve_and_bait` rule will pipe through bbduk.

**Note:** `GCA_000001405` is a placeholder accession used for illustration.
Look up real GBI accessions in the [GBI BioProject](https://www.ncbi.nlm.nih.gov/bioproject/?term=PRJNA489243)
or the Logan index at `s3://logan-pub/`. The real accession paths follow the
pattern `s3://logan-pub/u/<GCA_ACCESSION>/<GCA_ACCESSION>.unitigs.fa.zst`.

---

## 8. What's next

- **Phase 1:** Wire the real streaming command into `retrieve_and_bait` and test
  on 1–2 small GBI accessions.
- **rRNA seed set:** Build `resources/rrna_seeds.fa` before Phase 1 (see
  Guide 03 and the `reference-db-curator` subagent).
- **Add your accessions:** Edit `workflow/config/samplesheet.csv` to add real
  GBI accessions. Change `source` to `logan`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `endophynd: command not found` | Package not installed | `pip install -e ".[dev]"` |
| `snakemake: command not found` | Wrong conda env active | `conda activate endophynd` |
| `Cache config not found` | Wrong working directory | Run from the repo root |
| Hot cache full warning | `hot_cap_gb` too low for concurrent runs | Raise cap or reduce `max_parallel_accessions` |
| `MissingInputException` in Snakemake | Fixture file missing | Confirm `tests/fixtures/mock_its_reads.fa` exists |
