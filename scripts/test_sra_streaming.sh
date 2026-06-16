#!/usr/bin/env bash
# scripts/test_sra_streaming.sh
#
# Compare rRNA-seed baiting vs fungal-ITS-primer baiting on an SRA accession.
# Run from the project root with the retrieve_bait conda env active:
#
#   conda activate endophynd-retrieve-bait
#   bash scripts/test_sra_streaming.sh ERR15383529           # fungal WGS, 500K spots
#   bash scripts/test_sra_streaming.sh ERR15383529 4 0       # full dataset, 4 threads
#   bash scripts/test_sra_streaming.sh <PLANT_ACC> 4 500000  # plant WGS test
#
# Arguments:
#   $1  SRA accession (required)
#   $2  threads (default: 4)
#   $3  max spots to stream (default: 500000; use 0 for full dataset)
#       500K spots = ~1M PE reads, fast test run (~1-2 min)
#
# Outputs land in /tmp/<ACC>_*.  Nothing is written to the hot cache.

set -euo pipefail

ACC="${1:?Usage: $0 <ACCESSION> [THREADS] [MAX_SPOTS]}"
THREADS="${2:-4}"
MAX_SPOTS="${3:-500000}"

SEEDS="resources/rrna_seeds.fa"
PRIMERS="resources/its_primers.fa"
MINLEN=100

OUT_SEEDS="/tmp/${ACC}_seeds.fa"
OUT_PRIMERS="/tmp/${ACC}_primers.fa"
STATS_SEEDS="/tmp/${ACC}_seeds_stats.txt"
STATS_PRIMERS="/tmp/${ACC}_primers_stats.txt"
PEEK="/tmp/${ACC}_peek.fq"

# ── Spot-limit flag ────────────────────────────────────────────────────────
if [ "$MAX_SPOTS" -gt 0 ] 2>/dev/null; then
    SPOT_FLAG="--maxSpotId $MAX_SPOTS"
    SPOT_DESC="first $MAX_SPOTS spots"
else
    SPOT_FLAG=""
    SPOT_DESC="full dataset"
fi

echo "================================================================"
echo "SRA streaming bait comparison: $ACC  ($SPOT_DESC)"
echo "================================================================"
echo "Seeds:    $SEEDS  ($(grep -c '^>' $SEEDS) seqs, k=31)"
echo "Primers:  $PRIMERS  ($(grep -c '^>' $PRIMERS) seqs, k=20)"
echo ""

# ── Sanity-check: peek at the first 8 lines to confirm interleaved format ──
echo "--- Verifying fasterq-dump --split-spot output format ---"
fasterq-dump "$ACC" \
    --stdout --split-spot --skip-technical \
    --threads "$THREADS" \
    --maxSpotId 4 \
    2>/dev/null \
    > "$PEEK"

echo "First 8 lines of streamed output (should alternate /1 and /2 reads):"
head -8 "$PEEK"
echo ""

# ── Run 1: rRNA seeds, k=31 ───────────────────────────────────────────────
echo "--- Run 1: rRNA seeds (k=31, hdist=1) ---"
fasterq-dump "$ACC" \
    --stdout --split-spot --skip-technical \
    --threads "$THREADS" \
    $SPOT_FLAG \
    2>/dev/null \
  | bbduk.sh \
      in=stdin.fq \
      ref="$SEEDS" \
      outm="$OUT_SEEDS" \
      stats="$STATS_SEEDS" \
      k=31 hdist=1 minlength="$MINLEN" \
      threads="$THREADS" \
      2>&1

echo ""

# ── Run 2: fungal ITS primers, k=20 ───────────────────────────────────────
echo "--- Run 2: fungal ITS primers (k=20, hdist=1) ---"
fasterq-dump "$ACC" \
    --stdout --split-spot --skip-technical \
    --threads "$THREADS" \
    $SPOT_FLAG \
    2>/dev/null \
  | bbduk.sh \
      in=stdin.fq \
      ref="$PRIMERS" \
      outm="$OUT_PRIMERS" \
      stats="$STATS_PRIMERS" \
      k=20 hdist=1 minlength="$MINLEN" \
      threads="$THREADS" \
      2>&1

echo ""

# ── Summary ────────────────────────────────────────────────────────────────
NSEEDS=$(grep -c '^>' "$OUT_SEEDS" 2>/dev/null || echo 0)
NPRIMERS=$(grep -c '^>' "$OUT_PRIMERS" 2>/dev/null || echo 0)
TOTAL=$(awk '/^#Total/{print $2}' "$STATS_SEEDS")

echo "================================================================"
echo "SUMMARY: $ACC  ($SPOT_DESC)"
echo "================================================================"
printf "%-35s %10s  %s\n" "Bait set" "Reads" "% of total"
printf "%-35s %10s  %s\n" "---" "---" "---"
printf "%-35s %10s  %.4f%%\n" "rRNA seeds (k=31)"      "$NSEEDS"   "$(awk "BEGIN{printf \"%.4f\", $NSEEDS/$TOTAL*100}")"
printf "%-35s %10s  %.4f%%\n" "ITS primers (k=20)"     "$NPRIMERS" "$(awk "BEGIN{printf \"%.4f\", $NPRIMERS/$TOTAL*100}")"
echo ""
echo "Total reads processed: $TOTAL"
echo ""
echo "Baited sequences:"
echo "  Seeds:   $OUT_SEEDS"
echo "  Primers: $OUT_PRIMERS"
echo "Full bbduk stats:"
echo "  $STATS_SEEDS"
echo "  $STATS_PRIMERS"
