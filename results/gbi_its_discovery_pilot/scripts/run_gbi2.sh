#!/bin/bash
# Full-depth ITS recovery for the GBI positive-vs-negative comparison.
# Sequential (one dataset at a time) because fasterq-dump scratch is ~193GB/dataset.
set -uo pipefail

PROJ=/home/harte/endophynd/endophynd
BBDUK=$PROJ/.snakemake/conda/3edd7c30aca4e2f134ca34d85cf2d658_/bin/bbduk.sh
ITSX=$PROJ/.snakemake/conda/0d2d4e6e54655b1f7f63102894e5248e_/bin/ITSx
VSEARCH=$PROJ/.snakemake/conda/0d2d4e6e54655b1f7f63102894e5248e_/bin/vsearch
OUT=/home/harte/endophynd_cache/cold/tmp/gbi_discovery
SRADIR=/home/harte/endophynd_cache/cold/tmp/sra
SCRATCH=/home/harte/endophynd_cache/cold/tmp/fqd_scratch
mkdir -p "$OUT" "$SRADIR" "$SCRATCH"
cd "$PROJ"

log(){ echo "[$(date -u +%H:%M:%SZ)] $*"; }
clean_scratch(){ rm -rf "$SCRATCH"/fasterq.tmp.* 2>/dev/null; }
trap clean_scratch EXIT

run_one(){
  ACC=$1; LABEL=$2
  log "==================== $ACC ($LABEL) ===================="
  FREEG=$(df -BG "$SRADIR" | tail -1 | awk '{gsub("G","",$4); print $4}')
  log "[$ACC] free disk: ${FREEG}G"
  if [ "$FREEG" -lt 40 ]; then log "[$ACC] ABORT: <40G free"; return 1; fi

  if [ ! -f "$SRADIR/$ACC/$ACC.sra" ]; then
    log "[$ACC] prefetch (full .sra)..."
    prefetch "$ACC" --max-size 50g -O "$SRADIR" >"$OUT/$ACC.prefetch.log" 2>&1 \
      || { log "[$ACC] PREFETCH FAILED"; return 1; }
  else
    log "[$ACC] .sra already present (reusing)"
  fi
  SRA="$SRADIR/$ACC/$ACC.sra"
  log "[$ACC] .sra size: $(du -h "$SRA" | cut -f1)"

  # fastq-dump (legacy) streams from local .sra with negligible scratch and a stable
  # single-stream parser; bbduk int=f threads=4 (the multithreaded stdin reader
  # misaligns FASTQ records at threads=16 -> "missing plus" crash). bbduk paces it.
  log "[$ACC] fastq-dump(stream local .sra) -> bbduk bait int=f threads=4 (rrna_seeds, k31 hdist1 minlen100)..."
  fastq-dump --split-spot --skip-technical -Z "$SRA" 2>"$OUT/$ACC.fqd.err" \
    | "$BBDUK" in=stdin.fq int=f ref=resources/rrna_seeds.fa \
        outm="$OUT/$ACC.baited.fa" stats="$OUT/$ACC.bait_stats.txt" \
        k=31 hdist=1 minlength=100 threads=4 2>"$OUT/$ACC.bbduk.err"
  NBAIT=$(grep -c '^>' "$OUT/$ACC.baited.fa" 2>/dev/null || echo 0)
  log "[$ACC] baited reads: $NBAIT"
  [ "$NBAIT" -eq 0 ] && { log "[$ACC] 0 baited — aborting this dataset"; rm -rf "$SRADIR/$ACC"; return 1; }

  log "[$ACC] derep (exact dups -> uniques, keep abundance)..."
  "$VSEARCH" --derep_fulllength "$OUT/$ACC.baited.fa" --sizeout --minseqlength 80 \
     --output "$OUT/$ACC.derep.fa" --threads 16 2>"$OUT/$ACC.derep.err"
  NDEREP=$(grep -c '^>' "$OUT/$ACC.derep.fa" 2>/dev/null || echo 0)
  log "[$ACC] unique seqs: $NDEREP"

  log "[$ACC] ITSx (extract ITS; Fungi+plant profiles)..."
  "$ITSX" -i "$OUT/$ACC.derep.fa" -o "$OUT/$ACC.itsx" --cpu 16 --multi_thread T \
     -t F,T --save_regions all --partial 50 --minlen 50 --heuristics T --preserve T \
     >"$OUT/$ACC.itsx.log" 2>&1 || log "[$ACC] ITSx returned non-zero"
  for f in ITS1 ITS2; do
    n=$(grep -c '^>' "$OUT/$ACC.itsx.$f.fasta" 2>/dev/null || echo 0); log "[$ACC]   $f seqs: $n"
  done
  log "[$ACC] ITSx origin breakdown:"
  sed -n '/preliminary origin/,/^----/p' "$OUT/$ACC.itsx.summary.txt" 2>/dev/null \
    | grep -E ':[[:space:]]*[0-9]' | awk '$NF>0' | sed "s/^/[$ACC]     /"

  log "[$ACC] cleanup .sra..."
  rm -rf "$SRADIR/$ACC"
  log "[$ACC] DONE"
}

run_one SRR30183952 Silene_verecunda_D28-POSITIVE
run_one SRR30183458 Streptanthus_glandulosus_D28-NEGATIVE
log "ALL DONE"
