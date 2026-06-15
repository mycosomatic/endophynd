#!/usr/bin/env python3
"""
Parse ITSx output, apply informative-length gate, write gated FASTA + report.

Called by the annotate_and_gate Snakemake rule immediately after ITSx finishes.
Reads the ITSx positions file to find locus coordinates, gates each sequence on
informative-region length (using gate.py thresholds), and writes:
  - gated FASTA:  sequences whose best locus passes the gate (fine or coarse)
  - gate report:  TSV with one row per ITSx-detected sequence
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from endophynd.gate import GateDecision, GateEngine

# Priority order: ITS1 and ITS2 are the primary fungal barcoding loci.
LOCUS_PRIORITY = ["ITS1", "ITS2", "LSU", "SSU", "5.8S"]


def parse_positions(path: Path) -> dict:
    """
    Parse ITSx positions.txt → {seq_id: {locus: bp_length}}.

    Tab-delimited columns: Name, Length, SSU, ITS1, 5.8S, ITS2, LSU, [Comment]
    Each region cell is "start-end" (1-based, inclusive) or "Not found".
    """
    result: dict = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 7:
                continue
            seq_id = cols[0]
            region_map = {
                "SSU": cols[2],
                "ITS1": cols[3],
                "5.8S": cols[4],
                "ITS2": cols[5],
                "LSU": cols[6],
            }
            found: dict = {}
            for locus, val in region_map.items():
                v = val.strip()
                if v and v not in ("Not found", "N/A", "-"):
                    try:
                        s, e = v.split("-")
                        found[locus] = int(e) - int(s) + 1
                    except ValueError:
                        pass
            if found:
                result[seq_id] = found
    return result


def read_fasta(path: Path) -> dict:
    """Read FASTA → {seq_id: sequence_string}."""
    seqs: dict = {}
    hdr: str | None = None
    parts: list = []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip()
            if line.startswith(">"):
                if hdr is not None:
                    seqs[hdr[1:].split()[0]] = "".join(parts)
                hdr = line
                parts = []
            elif hdr is not None:
                parts.append(line)
        if hdr is not None:
            seqs[hdr[1:].split()[0]] = "".join(parts)
    return seqs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baited", required=True, help="Baited FASTA from retrieve_and_bait")
    ap.add_argument("--itsx-prefix", required=True, help="ITSx output prefix")
    ap.add_argument("--params", required=True, help="Path to params.yml")
    ap.add_argument("--gate-report", required=True)
    ap.add_argument("--gated-out", required=True)
    args = ap.parse_args()

    with open(args.params) as fh:
        params = yaml.safe_load(fh)
    engine = GateEngine.from_config(params)

    positions_path = Path(f"{args.itsx_prefix}.positions.txt")
    if not positions_path.exists():
        print(f"[gate] WARNING: no ITSx positions file at {positions_path}", file=sys.stderr)
        Path(args.gate_report).write_text("read_id\tlocus\tinformative_bp\tgate_decision\n")
        Path(args.gated_out).write_text("")
        return

    detections = parse_positions(positions_path)
    n_detected = len(detections)

    # Load baited sequences once — passing sequences are written from this dict.
    baited = read_fasta(Path(args.baited))

    n_fine = n_coarse = n_discard = 0

    with open(args.gate_report, "w") as rep_fh, open(args.gated_out, "w") as out_fh:
        rep_fh.write("read_id\tlocus\tinformative_bp\tgate_decision\n")

        for seq_id, locus_lengths in detections.items():
            locus = next((l for l in LOCUS_PRIORITY if l in locus_lengths), None)
            informative_bp = locus_lengths.get(locus, 0) if locus else 0
            gate_dec = (
                engine.decide(locus, informative_bp) if locus else GateDecision.DISCARD
            )

            rep_fh.write(
                f"{seq_id}\t{locus or 'none'}\t{informative_bp}\t{gate_dec.value}\n"
            )

            if gate_dec == GateDecision.FINE:
                n_fine += 1
            elif gate_dec == GateDecision.COARSE:
                n_coarse += 1
            else:
                n_discard += 1
                continue

            if seq_id in baited:
                out_fh.write(
                    f">{seq_id} locus={locus or 'none'}"
                    f" informative_bp={informative_bp}"
                    f" gate={gate_dec.value}\n"
                    f"{baited[seq_id]}\n"
                )

    print(
        f"[gate] detected={n_detected} fine={n_fine} coarse={n_coarse} discard={n_discard}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
