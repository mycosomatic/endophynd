# Methods summary — targeted recovery of query DNA from Logan/SRA datasets

*A concise, manuscript-ready précis of the targeted-search method and its first
application (the GBI *Alternaria* scan + calibration). Source of truth for the
details: `docs/decisions.md` (D27–D29), `results/alternaria_vs_gbi10/REPORT.md`,
`results/alternaria_vs_gbi10/calibration/README.md`. Numbers are tied to git
commit and `results/alternaria_vs_gbi10/provenance.json`.*

---

## What the method answers (scope)

Given a query sequence or genome, the method identifies **which sequencing datasets
contain DNA matching the query**, and recovers the matching reads/unitigs. A hit
indicates the matching DNA was present in a dataset's reads; it does **not**
establish that the source organism was alive, in, or on the sampled tissue
(endophyte, surface contaminant, laboratory/kit contaminant, and index-hopping are
not distinguished). The approach is therefore a hypothesis generator for follow-up,
with statistical value emerging at scale and for less contaminant-prone taxa.

## Targeted recovery (reference inversion)

For each target dataset, compressed Logan unitigs were streamed directly from the
public S3 bucket (`s3://logan-pub/u/<accession>/<accession>.unitigs.fa.zst`,
unauthenticated) through decompression (`zstd`) and alignment in a single pipe; no
whole dataset was written to disk. The **query was used as the alignment reference**
and the streamed dataset as the "reads" (reference inversion): no database of the
target dataset was built or downloaded. Alignments were produced with **minimap2**
(`-ax asm20 --secondary=no`) and mapped records retained with **samtools**
(`view -F 4`). For a multi-tier analysis the minimap2 minimum reported-score floor
was lowered (`-s 50`) so that sub-200 bp alignments were emitted from a single
alignment pass. Per-alignment identity was computed from the SAM `NM` tag and CIGAR
(matched bases ÷ alignment-block length) and alignment length as the CIGAR
alignment block. Raw-read (SRA) targets are supported via an equivalent
`fasterq-dump --stdout` stream; rDNA/divergent queries use **blastn** in place of
minimap2.

## Datasets

The query was a draft genome of an *Alternaria* sp. isolate (NS26-3-C2; 33.35 Mb,
83 contigs; md5 recorded in `provenance.json`). Targets were 10 deeply sequenced
(60–105 Gbp) Illumina WGS datasets of California-native plants from the Green Biome
Institute (NCBI BioProject search "green biome institute"), each present in Logan,
selected across diverse families (eudicots and monocots).

## Hit calling and tiers

Hits were retained at **≥95% identity** and reported at two length tiers from one
alignment: **≥200 bp (high-confidence)** and **≥125 bp (sensitive)**. Both tiers
were chosen with reference to the calibrated false-positive floor (below), not from
the data. Hits to conserved multi-copy loci (rDNA, mitochondrial) were identified by
reverse-classification (below) and reported separately from single-copy nuclear hits.

## Specificity calibration (false-positive floor)

Threshold specificity was calibrated empirically with a panel of nulls whose hits
are false positives by construction. A combined reference was built from the query
plus (i) four whole genomes that are biologically absent from the sampled plants —
*Morchella conica* (GCA_008079325.1), *Saccharomyces cerevisiae* (GCF_000146045.2),
*Boletus edulis* (GCA_054741165.1), and *Psilocybe zapotecorum* (GCA_040207405.1),
spanning increasing phylogenetic distance from the query — and (ii) a seeded
mononucleotide shuffle of the query genome (zero-homology, composition-matched). Each
null genome was first screened against the query (no ≥1 kb / ≥95% match, i.e. no
query-genome contamination). Datasets were re-aligned against this combined reference
in the same single pass, and hit counts per class were tabulated across an
identity × length grid.

At ≥95% identity / ≥200 bp the false-positive floor (the distant absent genomes and
the shuffle) was **zero** across all datasets, and zero from ≥125 bp upward; the
query signal exceeded the floor by >30×. The shuffle yielded zero hits at every
threshold tested (down to ≥50 bp), excluding chance alignment. *S. cerevisiae*
produced a small number of hits that were confirmed by reverse-classification to be
genuine yeast and were therefore excluded from the floor (yeast is a plausible real
presence — a common endophyte and contaminant — and is not a valid null). A stress
sweep with the lowered alignment floor located the breakdown point: false hits from
the distant nulls appeared only below ~75–100 bp and were traced to **conserved
rDNA** (>65% of sub-100 bp null hits clustered on a single null-genome rDNA contig),
not to low-complexity repeats; they were absent by ≥125 bp.

## Quality control

Because a targeted hit already constitutes a match to the query, hits were not
classified individually against an external database. Specificity was instead
established by the calibration above and confirmed by reverse-classifying a **seeded
random subset** of hits against the NCBI nucleotide database (blastn, `-remote`). In
the application, 39 of 40 randomly sampled ≥125 bp hits were classifiable and all
were fungal (38/39 *Alternaria* sect. *Alternaria*), with no plant or bacterial hits.

## Software and reproducibility

minimap2 v2.17-r941, samtools v1.14, BLAST+ (blastn) v2.16.0+, sourmash v4.9.4,
AWS CLI v1.22, zstd v1.5.7. All steps are scripted (`scripts/`); each result
directory records tool versions, parameters, accessions, query checksum, and the git
commit (`provenance.json`). Bulky intermediates are regenerable from the scripts.
Taxonomic calls within the *Alternaria* species complex are not resolvable at these
fragment lengths and are reported at section level.

## Limitations (for Discussion)

(1) Hits indicate DNA presence in reads, not organismal residency. (2) The
calibrated floor covers chance and distant-fungus cross-talk but **not** index-hopping
or co-sequencing carryover (a null cannot be index-hopped); provenance requires
flowcell metadata and per-locus read-coverage coherence. (3) No floor is measured for
an absent *close* relative of the query (none is constructible for a cosmopolitan
taxon), so within-complex resolution is a separate limit. (4) The first application is
a 10-dataset pilot; per-dataset error rates tighten with sample size, and multiple
queries × datasets require multiple-testing control.
