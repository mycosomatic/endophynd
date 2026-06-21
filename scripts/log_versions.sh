#!/usr/bin/env bash
# scripts/log_versions.sh
#
# Print all tool versions used by endophynd, plus reference file checksums.
# Run from the project root with the relevant conda env active:
#
#   conda activate endophynd-retrieve-bait && bash scripts/log_versions.sh
#
# Pipe to a file to archive alongside a run:
#   bash scripts/log_versions.sh | tee results/tool_versions.txt

set -uo pipefail

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
echo "=== endophynd tool versions  $STAMP ==="
echo ""

check() {
    local name="$1"; shift
    printf "%-22s " "$name"
    "$@" 2>&1 | head -1 || echo "(not found)"
}

echo "--- retrieve_bait env (conda activate endophynd-retrieve-bait) ---"
check "fasterq-dump"   fasterq-dump --version
check "bbduk.sh"       bbduk.sh --version
check "aws"            aws --version
check "zstd"           zstd --version
echo ""

echo "--- annotate env (conda activate endophynd-annotate) ---"
check "python3"        python3 --version
check "blastn"         blastn -version
check "ITSx"           ITSx --version
check "vsearch"        vsearch --version
echo ""

echo "--- classify env (conda activate endophynd-classify) ---"
check "qiime"          qiime --version
echo ""

echo "--- system ---"
check "snakemake"      snakemake --version
check "conda"          conda --version
echo ""
uname -a
echo ""

echo "--- reference files ---"
SEEDS="resources/rrna_seeds.fa"
PRIMERS="resources/its_primers.fa"
RDNA_REF="resources/rdna_ref.fa"
for f in "$SEEDS" "$PRIMERS" "$RDNA_REF"; do
    if [ -f "$f" ]; then
        COUNT=$(grep -c '^>' "$f" 2>/dev/null || echo "?")
        MD5=$(md5sum "$f" | cut -d' ' -f1)
        printf "  %-40s  %s seqs  md5=%s\n" "$f" "$COUNT" "$MD5"
    else
        printf "  %-40s  MISSING\n" "$f"
    fi
done
