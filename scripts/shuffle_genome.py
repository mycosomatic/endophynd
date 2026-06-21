#!/usr/bin/env python3
"""
Composition-matched zero-homology null: per-contig mononucleotide shuffle
(seeded → reproducible). Preserves each contig's length and exact base
composition but destroys all homology, so any alignment it produces against a
target is pure chance.

This is the "absolute floor" null: it shows whether the chosen identity/length
threshold admits random sequence at all. Repeat- and low-complexity-driven false
positives (which survive shuffling of real structure) are captured instead by the
real biologically-absent genome nulls in the calibration panel.
"""
from __future__ import annotations
import argparse
import random


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    def emit(h, seq, out):
        chars = list(seq)
        rng.shuffle(chars)
        s = "".join(chars)
        out.write(">" + h + "\n")
        for i in range(0, len(s), 80):
            out.write(s[i:i + 80] + "\n")

    with open(a.inp) as f, open(a.out, "w") as out:
        h, buf = None, []
        for line in f:
            if line.startswith(">"):
                if h is not None:
                    emit(h, "".join(buf), out)
                h = line[1:].strip().split()[0]
                buf = []
            else:
                buf.append(line.strip())
        if h is not None:
            emit(h, "".join(buf), out)


if __name__ == "__main__":
    main()
