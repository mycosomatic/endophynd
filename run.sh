#!/usr/bin/env bash
# Run the endophynd pipeline with full command logging.
#
# Every shell command Snakemake executes is printed before running
# (--printshellcmds) and captured alongside all rule output in a
# timestamped log file in the results directory.
#
# That log file is the primary reproducibility record: to re-run any step
# manually, copy the relevant command block from the log and paste it into
# a shell with the retrieve_bait or annotate conda env active.
#
# Usage:
#   bash run.sh                                     # 4 cores, default config
#   bash run.sh --cores 8                           # more cores
#   bash run.sh --dry-run                           # show DAG without running
#   bash run.sh --forcerun retrieve_and_bait        # re-run one rule
#   bash run.sh --configfile my_params.yml          # alternate config

set -euo pipefail

# ── Resolve results directory from config ─────────────────────────────────
RESULTS=$(python3 - <<'EOF'
import yaml, os
from pathlib import Path
c = yaml.safe_load(open('workflow/config/params.yml'))
cache = yaml.safe_load(open(c['cache_config']))
cold = Path(os.path.expanduser(cache['cold_dir']))
run_id = c.get('run_id') or 'run_001'
print(cold / 'results' / run_id)
EOF
)

mkdir -p "$RESULTS"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="$RESULTS/snakemake_${STAMP}.log"

# ── Log header ─────────────────────────────────────────────────────────────
{
    echo "================================================================"
    echo "endophynd run"
    echo "timestamp : $STAMP"
    echo "git       : $(git rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "branch    : $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    echo "host      : $(hostname -f 2>/dev/null || hostname)"
    echo "snakemake : $(snakemake --version 2>/dev/null || echo unknown)"
    echo "python    : $(python3 --version 2>&1)"
    echo "log       : $LOG"
    echo "================================================================"
    echo ""
} | tee "$LOG"

# ── Run ────────────────────────────────────────────────────────────────────
snakemake \
    --configfile workflow/config/params.yml \
    --printshellcmds \
    --reason \
    "$@" \
    2>&1 | tee -a "$LOG"

EXIT="${PIPESTATUS[0]}"

{
    echo ""
    echo "================================================================"
    echo "endophynd run END: $(date -u +%Y%m%dT%H%M%SZ)  exit=$EXIT"
    echo "================================================================"
} | tee -a "$LOG"

exit "$EXIT"
