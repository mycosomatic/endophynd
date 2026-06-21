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

    def streaming_command(
        self,
        output_path: str,
        seed_ref: str,
        k: int,
        hdist: int,
        minlength: int = 50,
        threads: int = 4,
        stats_path: Optional[str] = None,
    ) -> str:
        """
        Return a shell command string that streams + baits the input.

        The returned command writes baited FASTA to output_path.
        For Logan: the whole unitig file never touches disk — stream only.
        For local: bbduk reads the file directly.
        For SRA: stream raw reads via fasterq-dump → bait, platform-aware. The
        runtime authority for the discovery SRA command is workflow/Snakefile's
        retrieve_and_bait rule; this mirrors its core flags.
        """
        stats_arg = f"stats={stats_path}" if stats_path else ""

        if self.source == Source.LOCAL:
            return (
                f"bbduk.sh in={self.local_path} ref={seed_ref} "
                f"outm={output_path} {stats_arg} "
                f"k={k} hdist={hdist} minlength={minlength} threads={threads}"
            ).strip()

        if self.source == Source.LOGAN:
            acc = self.accession
            s3_url = f"s3://logan-pub/u/{acc}/{acc}.unitigs.fa.zst"
            return (
                f"aws s3 cp {s3_url} - --no-sign-request "
                f"| zstdcat "
                f"| bbduk.sh in=stdin.fa ref={seed_ref} "
                f"outm={output_path} {stats_arg} "
                f"k={k} hdist={hdist} minlength={minlength} threads={threads}"
            ).strip()

        if self.source == Source.SRA:
            # Stream raw reads via fasterq-dump → bait. Long-read platforms are
            # single-fragment (no --split-spot / no interleaving).
            acc = self.accession
            long_read = self.platform in (Platform.PACBIO, Platform.NANOPORE)
            split = "" if long_read else "--split-spot"
            inter = "int=f" if long_read else "int=t"
            return (
                f"fasterq-dump --stdout --skip-technical {split} --threads {threads} {acc} "
                f"| bbduk.sh in=stdin.fq {inter} ref={seed_ref} "
                f"outm={output_path} {stats_arg} "
                f"k={k} hdist={hdist} minlength={minlength} threads={threads}"
            ).strip()

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
