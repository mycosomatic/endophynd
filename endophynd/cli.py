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
