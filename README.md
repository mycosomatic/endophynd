# endophynd

Recover and classify fungal rDNA (ITS, LSU, SSU) from Logan/SRA data at the
read level, producing QIIME2-compatible feature tables and metabarcoding-style
reports.

## Quick start (Phase 0 — scaffold only)

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

- [x] Phase 0 — scaffold, config, cache manager, CLI skeleton, fixtures
- [ ] Phase 1 — read-level discovery MVP (Logan unitigs, streaming)
- [ ] Phase 1.5 — calibration map + mock community
- [ ] Phase 2 — multi-locus classification + HTML report
- [ ] Phase 3 — local raw-read recovery (Illumina)
- [ ] Phase 3.5 — Logan vs raw SRA concordance benchmark
- [ ] Phase 4 — targeted mode (query-as-reference)
- [ ] Phase 5 — long-read paths
- [ ] Phase 6 — Streamlit GUI
- [ ] Phase 7 — cloud scale-out (deferred)
