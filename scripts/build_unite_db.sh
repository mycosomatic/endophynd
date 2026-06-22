#!/usr/bin/env bash
# Build the UNITE classification indices used by the discovery `classify` rule (D30).
#
# Input: the UNITE general FASTA release for Fungi (download from
#   https://doi.org/10.15156/BIO/3301229  — v10.0, 2025-02-19 was validated).
# Output (in <db_dir>/unite/): a blastn DB (unite_blast.*) — the primary classifier —
#   and a SINTAX-formatted FASTA (unite_sintax.fasta) for optional corroboration.
#
# Usage:
#   scripts/build_unite_db.sh <unite_general_release.fasta> [db_dir]
# db_dir defaults to $ENDOPHYND_DB or ~/endophynd_cache/db
set -euo pipefail

SRC="${1:?path to UNITE general FASTA release required}"
DB_DIR="${2:-${ENDOPHYND_DB:-$HOME/endophynd_cache/db}}/unite"
mkdir -p "$DB_DIR"

[ -f "$SRC" ] || { echo "[build_unite_db] not found: $SRC" >&2; exit 1; }
N=$(grep -c '^>' "$SRC")
echo "[build_unite_db] source: $SRC ($N sequences)"
echo "[build_unite_db] md5: $(md5sum "$SRC" | cut -d' ' -f1)"

# blastn DB (primary classifier). No -parse_seqids: keep the full UNITE header as
# the subject id so taxonomy is parseable from blast output (Name|ACC|SH|type|k__...).
makeblastdb -in "$SRC" -dbtype nucl -out "$DB_DIR/unite_blast" -title "UNITE_Fungi" >/dev/null
echo "[build_unite_db] wrote $DB_DIR/unite_blast.*"

# SINTAX-formatted reference (corroboration only): k__Fungi;p__... -> tax=k:Fungi,p:...
awk -F'|' '
  /^>/ { acc=$2; sh=$3; tax=$5; gsub(/__/,":",tax); gsub(/;/,",",tax);
         print ">" acc "|" sh ";tax=" tax; next } { print }
' "$SRC" > "$DB_DIR/unite_sintax.fasta"
echo "[build_unite_db] wrote $DB_DIR/unite_sintax.fasta"
echo "[build_unite_db] done."
