"""
Platform / source detection and routing.

Given a sample row from the sample sheet, determine:
  - source  (logan | sra | local)
  - platform (illumina | nanopore | pacbio | synthetic)
  - input_type (reads | unitigs | contigs)

Returns a RetrievalRoute that the retrieve_and_bait rule uses to build its
streaming command.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Source(str, Enum):
    LOGAN = "logan"
    SRA = "sra"
    LOCAL = "local"


class Platform(str, Enum):
    ILLUMINA = "illumina"
    NANOPORE = "nanopore"
    PACBIO = "pacbio"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class InputType(str, Enum):
    READS = "reads"
    UNITIGS = "unitigs"
    CONTIGS = "contigs"


@dataclass
class RetrievalRoute:
    source: Source
    platform: Platform
    input_type: InputType
    accession: Optional[str]
    local_path: Optional[str]

    def streaming_command(self, output_path: str, seed_ref: str, k: int, hdist: int) -> str:
        """
        Return a shell command that streams + baits the input, writing to output_path.
        Phase 0: only 'local' source is implemented. Logan and SRA are stubs with
        the real command embedded as a comment so Phase 1 can uncomment them.
        """
        if self.source == Source.LOCAL:
            return (
                f"bbduk.sh in={self.local_path} ref={seed_ref} "
                f"outm={output_path} k={k} hdist={hdist}"
            )

        if self.source == Source.LOGAN:
            acc = self.accession
            # Real Phase 1 command:
            # aws s3 cp s3://logan-pub/u/{acc}/{acc}.unitigs.fa.zst - --no-sign-request \
            #   | zstdcat \
            #   | bbduk.sh in=stdin.fa ref={seed_ref} outm={output_path} k={k} hdist={hdist}
            raise NotImplementedError(
                f"Logan streaming not yet implemented (Phase 1). Accession: {acc}"
            )

        if self.source == Source.SRA:
            acc = self.accession
            # Real Phase 3 command (SRA path):
            # fastq-dump --stdout {acc} \
            #   | bbduk.sh in=stdin.fq ref={seed_ref} outm={output_path} k={k} hdist={hdist}
            raise NotImplementedError(
                f"SRA streaming not yet implemented (Phase 3). Accession: {acc}"
            )

        raise ValueError(f"Unknown source: {self.source}")


def route_sample(sample: dict) -> RetrievalRoute:
    """Parse a sample-sheet row into a RetrievalRoute."""
    source_str = sample.get("source", "local").lower()
    source = Source(source_str)

    platform_str = sample.get("platform", "unknown").lower()
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.UNKNOWN

    input_type_str = sample.get("input_type", "reads").lower()
    try:
        input_type = InputType(input_type_str)
    except ValueError:
        input_type = InputType.READS

    accession = sample.get("accession") if source != Source.LOCAL else None
    local_path = sample.get("accession") if source == Source.LOCAL else None

    return RetrievalRoute(
        source=source,
        platform=platform,
        input_type=input_type,
        accession=accession,
        local_path=local_path,
    )
