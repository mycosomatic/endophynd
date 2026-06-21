# endophynd

Recover and classify fungal rDNA (ITS, LSU, SSU) from Logan/SRA data at the
read level, producing QIIME2-compatible feature tables and metabarcoding-style
reports.

## Quick start

```bash
mamba env create -f envs/base.yml
conda activate endophynd
pip install -e .
endophynd --help
snakemake --configfile workflow/config/params.yml --cores 1 --dry-run
```

## Design

See `endophynd_development_plan.md` for the full design and roadmap.  
See `docs/decisions.md` for the append-only decision log.

## Phase status

Phases were built out of order: the targeted-search engine (Phase 4) and the SRA
streaming path landed early because a concrete application drove them. Calibration,
multi-locus classification, and the reporting/benchmark phases remain open. Status is
deliberately conservative — see `docs/decisions.md` for what each entry actually claims.

- [x] Phase 0 — scaffold, config, cache manager, CLI skeleton, fixtures
- [x] Phase 1 — read-level discovery MVP (Logan unitigs, streaming) — functional;
  validated on real Logan data (ERR15383529)
- [ ] Phase 1.5 — calibration map + mock community *(not started — gating thresholds are
  still post-hoc/uncalibrated)*
- [ ] Phase 2 — multi-locus classification + HTML report *(not started)*
- [x] Phase 3 — local raw-read / SRA streaming recovery (Illumina + platform tiers) —
  `source=sra` path landed in the triage and retrieve_and_bait rules (D21/D24/D25);
  the live SRA stream still needs end-to-end validation
- [ ] Phase 3.5 — Logan vs raw SRA concordance benchmark *(not started)*
- [x] Phase 4 — targeted mode (query-as-reference) — `endophynd target` engine built
  (D27): both aligners, BioProject expansion, 23 passing tests, re-found the RPB2 marker
  on real Logan data. First application is a **10-dataset GBI pilot scan**
  (`results/alternaria_vs_gbi10/`, D28) — hypothesis-generating, not a validated assay;
  the SRA-source branch of `target` is not yet validated on a live stream
- [ ] Phase 5 — long-read paths *(ONT/PacBio quality tiers defined in D25; paths not
  built)*
- [ ] Phase 6 — Streamlit GUI
- [ ] Phase 7 — cloud scale-out (deferred)
