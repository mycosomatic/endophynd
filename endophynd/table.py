"""
Feature table assembly.

Takes per-sample counts TSV + taxonomy TSV and produces:
  - BIOM (biom-format)
  - TSV mirror
  - QIIME2 .qza (FeatureTable[Frequency] + FeatureData[Taxonomy])

Phase 0: stubs only; real implementation in Phase 1.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional


def counts_to_biom_json(counts_tsv: Path, sample_id: str) -> dict:
    """
    Build a minimal BIOM v1.0 dict from a counts TSV.
    (Real BIOM construction via biom-format in Phase 1.)
    """
    features = []
    data = []

    with open(counts_tsv) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            fid = row.get("feature_id") or row.get("Feature ID") or f"feat_{i:04d}"
            count = int(row.get(sample_id, 0))
            features.append({"id": fid, "metadata": None})
            data.append([i, 0, count])  # (feature_index, sample_index, count)

    return {
        "id": None,
        "format": "Biological Observation Matrix 1.0.0",
        "type": "OTU table",
        "rows": features,
        "columns": [{"id": sample_id, "metadata": None}],
        "data": data,
        "matrix_type": "sparse",
        "matrix_element_type": "int",
        "shape": [len(features), 1],
    }


def write_stub_qza(output_path: Path, sample_id: str, counts_tsv: Path) -> None:
    """
    Write a placeholder .qza file.
    Phase 0 only — not a real QIIME2 artifact.
    Phase 1 will use `qiime tools import` instead.
    """
    import zipfile

    biom = counts_to_biom_json(counts_tsv, sample_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(output_path), "w") as zf:
        zf.writestr(
            "STUB_README.txt",
            f"Phase 0 stub. Not a valid QIIME2 artifact.\nSample: {sample_id}\n",
        )
        zf.writestr(
            "biom.json",
            json.dumps(biom, indent=2),
        )
