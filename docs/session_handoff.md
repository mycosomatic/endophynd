# Session Handoff — Logan Unitig Discovery

*Last updated: 2026-06-15. Append new entries at the bottom.*

---

## What we learned in this session

### 1. Logan unitigs in rDNA regions are ~33 bp (k-mer floor)

**Finding**: `ERR15383529` (Alternaria alternata, PE150 Illumina) has rDNA-baited
unitigs with median=33 bp, max=70 bp (n=226,490).

**Why**: Logan uses a k=31 de Bruijn graph. The rDNA operon is tandemly repeated
(50–200 copies) with slight inter-copy variants. Almost every position in ITS1/ITS2
has a branch in the de Bruijn graph → assembler stops → unitig = one or two k-mers.
The conserved 5.8S region should produce longer unitigs (all copies identical → no
branches) but we haven't confirmed this yet.

**Implication**: This is k-mer analysis, not read analysis. Individual unitigs carry
the same information as a 33 bp k-mer. Classification tools designed for amplicons
(q2-feature-classifier) will not work. k-mer-based tools (Kraken2, minimap2 with
appropriate parameters, VSEARCH with short-read settings) are needed.

**Action**: Switch `classify` rule from `q2-feature-classifier` to Kraken2 or
minimap2 in Phase 2. Deferred; document the blocker here.

---

### 2. ITSx → BLAST swap was the right call

**Finding**: ITSx detected **0 sequences** from 226K Alternaria unitigs. BLAST
detected **5,186** (558 coarse + 4,628 discard with our current thresholds).

**Why**: ITSx uses HMM profiles to locate conserved SSU/LSU flanks surrounding ITS.
Logan unitigs at 33 bp contain no flanks; they're from the interior of the ITS
variable region. BLAST has no such requirement.

**Current state**: `scripts/assign_locus_blast.py` + `resources/rdna_ref.fa` (78
sequences: 28 SSU, 40 ITS, 10 LSU, built from existing seeds via `--no-fetch`).

**Improvement needed**: The Alternaria reference is only one sequence
(`LC769425.1`, Alternaria *sp.* P26-R1-3). Real *A. alternata* ITS sequences
differ enough in ITS1/ITS2 that alignment windows are only 61 bp. Run
`scripts/build_rdna_ref.py --email your@email.com` (with NCBI access) to fetch
actual *Alternaria alternata* ITS amplicons and expand the reference.

---

### 3. Gate thresholds must match the data (D18)

**Finding**: With amplicon-calibrated thresholds (fine=100 bp), zero sequences
passed as fine. Lowered to ITS fine=50 bp, SSU/LSU fine=60 bp.

**Status**: Provisional. Phase 1.5 calibration map will replace these with
data-driven per-locus thresholds.

---

### 4. bbduk `minlength=50` is not filtering as expected

**Finding**: The baited file contains sequences as short as 3 bp despite
`minlength=50` in the Snakemake rule. The Logan FASTA piped via `zstdcat` to
`bbduk.sh in=stdin.fa` may bypass length filtering.

**Action (next session)**: Verify whether bbduk applies `minlength` to FASTA
stdin input. If not, add an explicit post-bait filter:
```bash
bbduk.sh ... | awk '...'   # or seqkit seq -m 50
```
Or switch to `minlen` (alternate parameter name) or `ml` (alias).

---

### 5. q2-feature-classifier is the wrong classifier for unitig data

**Finding**: q2-feature-classifier is trained on and designed for amplicon-length
sequences (300–500 bp). At 33 bp, it will either fail or give meaningless output.

**Candidates to replace it**:
- **Kraken2**: k-mer database, excellent at short fragments, fast
- **minimap2**: `--cs -ax sr` with a short-read preset; can align 30 bp+ to a
  reference and report taxonomy from hit sequence name
- **VSEARCH `--usearch_global`**: works at short lengths if `--minseqlength` and
  `--id` are tuned (id=0.80 for short reads)

**Action**: Phase 2 task. Update `classify` rule. Kraken2 is the strongest
candidate because it's purpose-built for k-mer-level taxonomy.

---

## What to test next

### A. Test on a different Logan accession

Goal: determine if the 33 bp unitig finding is universal across Logan or specific
to Alternaria/fungi.

Good targets:
- Another Ascomycete with known ITS (e.g., Fusarium, Aspergillus) — compare
  unitig length distribution
- A Basidiomycete (e.g., Agaricus bisporus) — ITS typically longer
- A well-characterized metagenome where expected taxa are known

Add to `workflow/config/samplesheet.csv` and re-run.

### B. Cache sequences for manual inspection

The cleanup rule deletes hot-cache files after classification. To keep them:

```yaml
# workflow/config/params.yml
delete_transient_after_classify: false
```

Then after a run, the baited.fa and gate_report.tsv survive in:
```
~/endophynd_cache/hot/baited/<sample>.baited.fa
~/endophynd_cache/hot/gated/<sample>.gated.fa
~/endophynd_cache/hot/gated/<sample>.gate_report.tsv
```

To pull a random sample of sequences with their BLAST locus labels:
```bash
# Join gate_report to baited sequences for manual inspection
python3 - <<'EOF'
import csv, random
report = {r['read_id']: r for r in csv.DictReader(
    open('~/endophynd_cache/hot/gated/ERR15383529.gate_report.tsv'), delimiter='\t')}
# sample 50 ITS sequences that passed gate
its_passing = [k for k,v in report.items()
               if v['locus']=='ITS' and v['gate_decision'] in ('fine','coarse')]
for seq_id in random.sample(its_passing, min(50, len(its_passing))):
    r = report[seq_id]
    print(f"{seq_id}\t{r['locus']}\t{r['informative_bp']}bp\t{r['gate_decision']}")
EOF
```

### C. Expand the BLAST reference

Run from a machine with NCBI access:
```bash
# Rebuild seeds with ITS amplicons (new groups: ITS_Ascomycota, ITS_Basidiomycota,
# ITS_Pleosporales — replaces the empty 5.8S groups)
python scripts/build_rrna_seeds.py --email your@email.com

# Rebuild BLAST reference with NCBI ITS amplicons for major lineages
python scripts/build_rdna_ref.py --email your@email.com
```

Commit the new `resources/rrna_seeds.fa` and `resources/rdna_ref.fa`.

---

## Open questions

1. **Why is 5.8S not producing longer alignments?** 5.8S is ~155 bp and fully
   conserved. If a unitig covered the 5.8S region it should give a 155 bp
   alignment (fine). We don't see this. Is 5.8S simply not being baited (seed
   gaps), or are the 5.8S unitigs > 70 bp and bypassing the minlength bug?

2. **What fraction of the 1,884 bbduk "Contaminants" (high-k-mer-density hits)
   pass BLAST?** These are more likely true rDNA sequences. We'd expect longer
   alignments from them than from the 224K single-k-mer hits.

3. **Can the `outm` rate (0.83% = 1884/226428) be improved by tuning bbduk
   parameters?** Lower `hdist` (0 instead of 1) would reduce false positives.
   Or use `outm` with a HIGHER k (k=51, k=71) to require longer matches.

---

## Files changed this session

| File | Change |
|------|--------|
| `scripts/assign_locus_blast.py` | New — BLAST-based locus assignment (replaces ITSx) |
| `scripts/build_rdna_ref.py` | New — builds per-locus BLAST reference from seeds |
| `scripts/build_rrna_seeds.py` | Fix — 5.8S groups → ITS amplicon groups |
| `resources/rdna_ref.fa` | New — 78-sequence BLAST reference (28 SSU, 40 ITS, 10 LSU) |
| `envs/annotate.yml` | Add `blast>=2.14` |
| `workflow/Snakefile` | Replace ITSx with BLAST in `annotate_and_gate`; add rdna_ref guard |
| `workflow/config/params.yml` | Add ITS gate threshold; lower all thresholds for unitig reality |
| `docs/decisions.md` | Add D17 (BLAST over ITSx) and D18 (gate thresholds) |
| `tests/test_rrna_seeds.py` | Fix IUPAC alphabet test; fix provenance key assertion |
