# `refs/` — combined reference for the alternaria_vs_gbi10 scan

> **Note on git:** `refs/` is gitignored (see `../.gitignore`) because it holds bulky,
> re-creatable intermediates (`combined_ref.fa`, the `.mmi` index, `alt.sig`/`ctrl.sig`).
> This README is the one tracked file in here — force-add it with
> `git add -f results/alternaria_vs_gbi10/refs/README.md`.

`combined_ref.fa` is the single "query" reference that all 10 plant datasets were
streamed through by reference inversion (D05): the query is the reference; each plant
target is streamed *through* it; only matches are kept. It contains **114 sequences**
under three prefixes:

| Prefix    | n seqs | What it is | Source |
|-----------|-------:|------------|--------|
| `ALT_`    | 83 | The *Alternaria* sp. **NS26-3-C2** query genome — what we look FOR (33,349,952 bp). | Harte's cultured isolate, EGAP assembly: `NS26-3-C2_final_EGAP_assembly.fasta` (see below). |
| `CTRL_`   | 17 | *Saccharomyces cerevisiae* R64 — distant-fungus noise floor; if it lights up where ALT does, hits are non-specific. | NCBI `GCF_000146045.2`. |
| `FUNGAL_` | 14 | Conserved single-copy marker panel (RPB2/TEF1/β-tubulin etc.) — the "any-fungus" control. | `resources/fungal_markers.fa`. **DROPPED as a tooling failure (D28 Decision 3); NOT used in the corrected result (see REPORT.md §5).** Retained in the combined ref only for provenance/reproducibility of the original run. |

## Rebuild

```bash
REFDIR=results/alternaria_vs_gbi10/refs
mkdir -p "$REFDIR"

# 1. ALT_ — the query genome (supply NS26-3-C2_final_EGAP_assembly.fasta; see note below)
sed 's/^>/>ALT_/'  /path/to/NS26-3-C2_final_EGAP_assembly.fasta  >  "$REFDIR/combined_ref.fa"

# 2. CTRL_ — S. cerevisiae R64 (NCBI GCF_000146045.2), fetched and decompressed
sed 's/^>/>CTRL_/' GCF_000146045.2_R64_genomic.fna             >> "$REFDIR/combined_ref.fa"

# 3. FUNGAL_ — conserved-marker panel (DROPPED from the corrected result; kept for provenance)
sed 's/^>/>FUNGAL_/' resources/fungal_markers.fa               >> "$REFDIR/combined_ref.fa"

# 4. minimap2 index + sourmash signatures (k=31, scaled=1000)
minimap2 -d "$REFDIR/combined_ref.mmi" "$REFDIR/combined_ref.fa"
sourmash sketch dna -p k=31,scaled=1000 -o "$REFDIR/alt.sig"  <ALT_-only contigs>
sourmash sketch dna -p k=31,scaled=1000 -o "$REFDIR/ctrl.sig" <CTRL_-only contigs>
```

Prefix-counts to verify: `grep '^>' combined_ref.fa | cut -c1-6 | sort | uniq -c`
→ `83 ALT_NO`, `17 CTRL_N`, `14 FUNGAL`.

## The query genome must be supplied to reproduce

The `ALT_` contigs come from **`NS26-3-C2_final_EGAP_assembly.fasta`** — an
**unpublished** *Alternaria* isolate (EGAP assembly, 83 contigs, 33,349,952 bp). It is
**not** in this repo and cannot be downloaded from a public archive; you must obtain it
from the authors to reproduce the scan.

- md5 of the query genome: **NOT_COMPUTED** — `md5sum` could not be executed in the
  environment that wrote this file. Record it by running
  `md5sum /home/harte/Desktop/Ian/CoSp_Test5/Alternaria_sp_A2/NS26-3-C2/NS26-3-C2_final_EGAP_assembly.fasta`
  and copy the value here and into `../provenance.json` (`query_genome.md5`). The 83
  query contigs are also embedded as the `ALT_` records in `combined_ref.fa`, so the
  identity of the bytes used in this run is re-derivable from that file even before the
  checksum is filled in.
