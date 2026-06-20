#!/usr/bin/env bash
# Single-stream confidence scan of one plant Logan accession against the combined
# reference (ALT_ = our Alternaria genome, CTRL_ = distant-fungus control genome,
# FUNGAL_ = pan-fungal conserved-marker panel).
#
# One S3 download is tee'd to TWO consumers via FIFOs (both guaranteed to finish):
# minimap2 (alignment -> mapped SAM) and sourmash (k-mer sketch). Then the
# alignment profile and sourmash containment are computed. A `.done` flag marks a
# completed stream (an empty SAM is a valid result, so we can't test file size).
set -uo pipefail

RUN="$1"
RES=results/alternaria_vs_gbi10
REF="$RES/refs/combined_ref.fa"
PP="$RES/per_plant"
mkdir -p "$PP"
SAM="$PP/$RUN.sam"
SIG="$PP/$RUN.sig"

if [ ! -f "$PP/$RUN.done" ]; then
  TMPD=$(mktemp -d)
  P1="$TMPD/mm.fifo"; P2="$TMPD/sm.fifo"
  mkfifo "$P1" "$P2"
  # pipefail inside the subshell so a minimap2 failure (not just samtools) is caught.
  ( set -o pipefail; minimap2 -ax asm20 -t 4 --secondary=no "$REF" "$P1" 2>"$PP/$RUN.mm2.err" \
      | samtools view -F 4 - > "$SAM" ) & MM=$!
  ( sourmash sketch dna -p k=31,scaled=1000 "$P2" -o "$SIG" --name "$RUN" 2>"$PP/$RUN.sm.err" ) & SM=$!
  aws s3 cp "s3://logan-pub/u/$RUN/$RUN.unitigs.fa.zst" - --no-sign-request 2>"$PP/$RUN.aws.err" \
    | zstdcat | tee "$P1" > "$P2"
  STREAM_RC=$?            # set -o pipefail (top of script) → non-zero if aws/zstdcat/tee failed
  wait "$MM"; MM_RC=$?
  wait "$SM"; SM_RC=$?
  rm -rf "$TMPD"
  if [ "$STREAM_RC" = "0" ] && [ "$MM_RC" = "0" ] && [ "$SM_RC" = "0" ]; then
    touch "$PP/$RUN.done"
  else
    # CRITICAL: never cache or profile a failed/partial stream — that would read as
    # a false "no signal". Remove partial outputs so a rerun re-streams cleanly.
    echo "STREAM FAILED $RUN (stream=$STREAM_RC minimap2/samtools=$MM_RC sourmash=$SM_RC) — not caching" >&2
    rm -f "$SAM" "$SIG"
    exit 1
  fi
fi

# Profiling/containment run ONLY when the stream completed (.done exists).
if [ ! -f "$PP/$RUN.done" ]; then echo "no .done for $RUN — skipping profile" >&2; exit 1; fi

python3 scripts/confidence_profile.py --ref "$REF" --sam "$SAM" \
  --json "$PP/$RUN.profile.json" --alt-hits-out "$PP/$RUN.alt_unitigs.txt" >/dev/null

for TAG in alt ctrl; do
  sourmash prefetch "$RES/refs/$TAG.sig" "$SIG" --threshold-bp 0 2>/dev/null \
    | grep -iE 'distinct query hashes' > "$PP/$RUN.$TAG.containment.txt" || true
done
echo "done $RUN"
