# Guide 02 — Resolving a BioProject to its run accessions

**Purpose.** A BioProject (e.g. `PRJEB93827`, `PRJNA123456`) is an umbrella over
many sequencing runs. To search or process it you need its **run accessions**
(`SRR…`, `ERR…`, `DRR…`). This guide shows how to expand a BioProject in bulk.

Endophynd does this for you wherever a target/sample accepts a BioProject, but
the same one-liner is useful on its own.

---

## The tool: the ENA filereport API

[ENA](https://www.ebi.ac.uk/ena) exposes a no-key REST endpoint that lists the
runs in a project. It cross-references NCBI, so it works for **PRJEB** *and* most
**PRJNA** projects.

```bash
curl -s "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJEB93827&result=read_run&fields=run_accession&format=tsv"
```

Output is a TSV with a `run_accession` header followed by one accession per line:

```
run_accession
ERR15281745
ERR15281748
...
```

Add more `fields` to get metadata in the same call, e.g.
`fields=run_accession,library_strategy,instrument_platform,read_count,base_count`
— handy for triage (skip amplicon runs, flag huge ones) before any heavy work.

Save just the accessions to a file:

```bash
curl -s "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJEB93827&result=read_run&fields=run_accession&format=tsv" \
  | tail -n +2 > runs.txt
```

---

## Inside endophynd

The same expansion is built into target resolution
(`endophynd/target/resolve.py`):

```python
from endophynd.target.resolve import expand_bioproject
runs = expand_bioproject("PRJEB93827")   # -> ['ERR15281745', ...]
```

So you can hand a BioProject straight to the targeted search and it expands
automatically:

```bash
endophynd target --query markers.fa --targets PRJEB93827 --source auto --out results/proj
```

…or feed it a saved file of accessions:

```bash
endophynd target --query markers.fa --targets @runs.txt --source auto --out results/proj
```

---

## What success looks like

A non-empty list of `SRR/ERR/DRR` accessions. If you get an empty result:

- Double-check the accession (a typo, or a sample/experiment accession instead
  of a project).
- Some projects have no `read_run` records (e.g. assembly-only submissions) —
  there are simply no raw runs to resolve.
- Network/proxy issues: the API call needs outbound HTTPS to `ebi.ac.uk`.

## Note on Logan availability

Resolving a run accession does **not** mean Logan has assembled it. Under
`--source auto`, endophynd checks the Logan bucket per accession and falls back
to SRA where Logan is absent. To skip that per-accession check on large projects,
pass `--no-logan-check` (SRA is assumed when Logan presence is unknown).
