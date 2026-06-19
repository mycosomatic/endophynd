"""
Shared data model for targeted search (capability B).

Targeted mode inverts the reference (decision D05): the *query* is the tiny
reference, and each target dataset (Logan unitigs / SRA reads / a local FASTA)
is streamed *through* it by alignment.  No database of the dataset is ever built
or downloaded.

Vocabulary used throughout this package — kept deliberately explicit because
"target" and "query" are each overloaded in alignment tools:

  query        — the sequence(s) you are looking FOR (your reference panel:
                 a fungal genome, single-copy markers, or an rDNA barcode).
  target       — a dataset you are searching IN (one accession or local file:
                 the plant genome / SRA run you want to know "contains" the query).
  matched_seq  — a single Logan unitig or SRA read from a target that aligned to
                 the query.  This is the thing the user wants located.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Source(str, Enum):
    """Where a target's sequence data comes from."""
    LOGAN = "logan"   # stream s3://logan-pub/u/<acc>/<acc>.unitigs.fa.zst
    SRA = "sra"       # stream raw reads via fasterq-dump --stdout
    LOCAL = "local"   # a FASTA/FASTQ already on disk
    AUTO = "auto"     # decide per target (prefer Logan if present, else SRA)


class QueryType(str, Enum):
    """What kind of query this is — drives default aligner and source warnings."""
    GENOME = "genome"   # whole genome / single-copy markers → minimap2 + Logan
    RDNA = "rdna"       # rDNA / ITS barcode → blastn + SRA (Logan collapses rDNA, D20)
    AUTO = "auto"       # detect from the query sequence


class Aligner(str, Enum):
    MINIMAP2 = "minimap2"   # fast, near-identity; the verified Logan idiom
    BLASTN = "blastn"       # sensitive to divergence; length-agnostic
    AUTO = "auto"           # pick from query type


@dataclass
class Target:
    """One dataset to search in."""
    accession: str               # run accession (SRR/ERR/DRR) or a label for local files
    source: Source
    local_path: Optional[str] = None   # set when source == LOCAL
    bioproject: Optional[str] = None   # set if this target came from a BioProject expansion

    @property
    def label(self) -> str:
        """A stable, filesystem-safe identifier for output files."""
        if self.source == Source.LOCAL and self.local_path:
            # Use the file stem; fall back to accession.
            from pathlib import Path
            return Path(self.local_path).stem or self.accession
        return self.accession


@dataclass
class QuerySpec:
    """The prepared query: its file, type, and tool-specific reference handles."""
    fasta_path: str
    query_type: QueryType
    record_lengths: dict[str, int]      # query record id -> length (bp)
    blast_db_prefix: Optional[str] = None   # set once makeblastdb has run

    @property
    def total_bp(self) -> int:
        return sum(self.record_lengths.values())


@dataclass
class Hit:
    """A single matched Logan unitig / SRA read aligning to a query record."""
    matched_seq_id: str    # id of the unitig/read in the target dataset
    query_id: str          # id of the query record it aligned to
    identity: float        # fraction in [0, 1]
    aln_len: int           # alignment block length (bp)
    query_cov: float       # fraction of the query record covered by this alignment
    query_start: int
    query_end: int
    matched_seq: str = ""  # the matching dataset sequence (read, or aligned portion)
    strand: str = "+"


@dataclass
class TargetResult:
    """Outcome of searching one target."""
    accession: str
    source: Source
    status: str                       # ok | empty | absent | error
    hits: list[Hit] = field(default_factory=list)
    message: str = ""
    bioproject: Optional[str] = None

    @property
    def n_hits(self) -> int:
        return len(self.hits)

    @property
    def query_ids_hit(self) -> set[str]:
        return {h.query_id for h in self.hits}
