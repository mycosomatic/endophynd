"""
Endophynd CLI — Typer-based entry point.

Usage:
  endophynd run   --config workflow/config/params.yml --cores 4
  endophynd check --config workflow/config/params.yml
  endophynd cache --config workflow/config/cache.yml status
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from endophynd import __version__
from endophynd.cache import CacheManager

app = typer.Typer(
    name="endophynd",
    help="Recover and classify fungal rDNA from Logan/SRA data.",
    add_completion=False,
)
console = Console()
cache_app = typer.Typer(help="Inspect and manage the cache directories.")
app.add_typer(cache_app, name="cache")


# ---------------------------------------------------------------------------
# Default thresholds for `endophynd target` (overridable on the CLI).
# Kept here so the command signature stays readable.
# ---------------------------------------------------------------------------
_TARGET_DEFAULTS = {
    "min_identity": 0.80,
    "min_aln_len": 50,
    "min_query_cov": 0.0,
    "minimap2_preset": "asm20",
    "max_target_seqs": 5,
    "evalue": 1e-5,
    "jobs": 4,
    "threads": 4,
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"endophynd {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Endophynd — fungal rDNA recovery and classification toolkit."""


# ---------------------------------------------------------------------------
# endophynd run
# ---------------------------------------------------------------------------

@app.command()
def run(
    config: Path = typer.Option(
        Path("workflow/config/params.yml"),
        "--config", "-c",
        help="Path to params.yml",
        exists=True,
    ),
    cores: int = typer.Option(4, "--cores", "-j", help="Snakemake cores"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Snakemake dry run"),
    targets: Optional[list[str]] = typer.Argument(default=None, help="Specific Snakemake targets"),
) -> None:
    """Run the Endophynd pipeline via Snakemake."""
    cmd = [
        "snakemake",
        "--configfile", str(config),
        "--cores", str(cores),
        "--use-conda",
    ]
    if dry_run:
        cmd.append("--dry-run")
    if targets:
        cmd.extend(targets)

    console.print(f"[bold green]Running:[/bold green] {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# endophynd check
# ---------------------------------------------------------------------------

@app.command()
def check(
    config: Path = typer.Option(
        Path("workflow/config/params.yml"),
        "--config", "-c",
        help="Path to params.yml",
        exists=True,
    ),
) -> None:
    """Validate config files and check that cache directories are writable."""
    with open(config) as f:
        params = yaml.safe_load(f)

    cache_config_path = params.get("cache_config", "workflow/config/cache.yml")
    cache = CacheManager.from_config(cache_config_path)

    console.print(f"[bold]Cache directories:[/bold]")
    console.print(f"  hot:  {cache.hot_dir}")
    console.print(f"  cold: {cache.cold_dir}")
    console.print(f"  db:   {cache.db_dir}")

    for name, path in [("hot", cache.hot_dir), ("cold", cache.cold_dir), ("db", cache.db_dir)]:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        try:
            test_file.write_text("ok")
            test_file.unlink()
            console.print(f"  [green]✓[/green] {name} dir is writable")
        except OSError as e:
            console.print(f"  [red]✗[/red] {name} dir not writable: {e}")
            raise typer.Exit(1)

    console.print(f"\n[green]Config OK.[/green] Samplesheet: {params.get('samplesheet')}")


# ---------------------------------------------------------------------------
# endophynd target  (capability B — targeted search)
# ---------------------------------------------------------------------------

@app.command()
def target(
    query: Path = typer.Option(
        ..., "--query", "-q", exists=True,
        help="FASTA of query sequence(s) to look for (genome, markers, or rDNA).",
    ),
    targets: list[str] = typer.Option(
        ..., "--targets", "-t",
        help="Targets to search: run accessions (SRR/ERR/DRR), a BioProject "
             "(PRJNA/PRJEB), a local FASTA path, or @file. Repeatable / comma-separated.",
    ),
    out: Path = typer.Option(..., "--out", "-o", help="Output directory for results."),
    source: str = typer.Option(
        "auto", "--source", "-s",
        help="Where to read each target: auto | logan | sra | local.",
    ),
    query_type: str = typer.Option(
        "auto", "--query-type",
        help="auto | genome | rdna. Sets default aligner and pairing warnings (D20).",
    ),
    aligner: str = typer.Option(
        "auto", "--aligner",
        help="auto | minimap2 | blastn. auto: minimap2 for genome, blastn for rDNA.",
    ),
    min_identity: float = typer.Option(
        _TARGET_DEFAULTS["min_identity"], "--min-identity",
        help="Minimum alignment identity (0-1) to keep a hit.",
    ),
    min_aln_len: int = typer.Option(
        _TARGET_DEFAULTS["min_aln_len"], "--min-aln-len",
        help="Minimum alignment length (bp) to keep a hit.",
    ),
    min_query_cov: float = typer.Option(
        _TARGET_DEFAULTS["min_query_cov"], "--min-query-cov",
        help="Minimum fraction of the query record covered by a single hit.",
    ),
    minimap2_preset: str = typer.Option(
        _TARGET_DEFAULTS["minimap2_preset"], "--minimap2-preset",
        help="minimap2 -x preset (provisional pending mock-community calibration).",
    ),
    jobs: int = typer.Option(
        _TARGET_DEFAULTS["jobs"], "--jobs", "-J",
        help="Parallel targets to stream at once.",
    ),
    threads: int = typer.Option(
        _TARGET_DEFAULTS["threads"], "--threads",
        help="Threads per aligner invocation.",
    ),
    rdna_ref: Path = typer.Option(
        Path("resources/rdna_ref.fa"), "--rdna-ref",
        help="rDNA reference used for query-type auto-detection.",
    ),
    no_logan_check: bool = typer.Option(
        False, "--no-logan-check",
        help="Skip the per-accession Logan presence check under --source auto "
             "(faster for large BioProjects; SRA assumed when unsure).",
    ),
) -> None:
    """Point a query at target datasets and locate matching Logan unitigs / SRA reads."""
    from endophynd.target.models import Aligner, QueryType, Source
    from endophynd.target.run import run_targeted_search

    def _enum(enum_cls, value, flag):
        try:
            return enum_cls(value.lower())
        except ValueError:
            valid = ", ".join(e.value for e in enum_cls)
            console.print(f"[red]Invalid {flag}: '{value}'. Choose one of: {valid}[/red]")
            raise typer.Exit(2)

    try:
        summary = run_targeted_search(
            str(query),
            list(targets),
            out_dir=str(out),
            source=_enum(Source, source, "--source"),
            query_type=_enum(QueryType, query_type, "--query-type"),
            aligner=_enum(Aligner, aligner, "--aligner"),
            rdna_ref=str(rdna_ref),
            min_identity=min_identity,
            min_aln_len=min_aln_len,
            min_query_cov=min_query_cov,
            minimap2_preset=minimap2_preset,
            jobs=jobs,
            threads=threads,
            check_logan=not no_logan_check,
            log=lambda m: console.print(m),
        )
    except Exception as e:
        console.print(f"[red]Targeted search failed:[/red] {e}")
        raise typer.Exit(1)

    console.print(
        f"\n[green]✓[/green] {summary['n_hits']} hit(s) across "
        f"{summary['n_query_target_pairs']} query×target pair(s); "
        f"{summary['n_matched_sequences']} matching sequence(s) saved."
    )
    console.print(f"  Reverse-lookup table: {summary['outputs']['summary']}")


# ---------------------------------------------------------------------------
# endophynd cache status
# ---------------------------------------------------------------------------

@cache_app.command("status")
def cache_status(
    config: Path = typer.Option(
        Path("workflow/config/cache.yml"),
        "--config", "-c",
        help="Path to cache.yml",
    ),
) -> None:
    """Show hot cache usage vs cap."""
    if not config.exists():
        console.print(f"[red]Cache config not found:[/red] {config}")
        raise typer.Exit(1)

    cache = CacheManager.from_config(config)
    used = cache.hot_usage_gb() if cache.hot_dir.exists() else 0.0
    cap = cache.hot_cap_gb

    console.print(f"Hot cache: {cache.hot_dir}")
    console.print(f"  Used:  {used:.2f} GB")
    console.print(f"  Cap:   {cap:.1f} GB")
    console.print(f"  Free:  {cap - used:.2f} GB")

    if used / cap > 0.9:
        console.print("[yellow]Warning: hot cache >90% full.[/yellow]")


if __name__ == "__main__":
    app()
