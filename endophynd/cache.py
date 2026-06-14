"""
Hot / cold / DB cache manager.

Three directories:
  hot_dir   — internal SSD; transient per-accession files; size-capped.
  cold_dir  — external drive; finished results and archived inputs.
  db_dir    — reference databases; large, written once.

Paths come from cache.yml (or env-var overrides at runtime).

Usage:
  cache = CacheManager.from_config("workflow/config/cache.yml")
  cache.ensure_hot_space(needed_gb=2.0)
  baited_path = cache.hot("baited") / f"{accession}.baited.fa"
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml


class CacheManager:
    def __init__(self, hot_dir: Path, cold_dir: Path, db_dir: Path, hot_cap_gb: float):
        self.hot_dir = hot_dir
        self.cold_dir = cold_dir
        self.db_dir = db_dir
        self.hot_cap_gb = hot_cap_gb

    @classmethod
    def from_config(cls, config_path: str | Path) -> "CacheManager":
        """Load from a YAML config, respecting env-var overrides."""
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        def resolve(key: str, env_var: str) -> Path:
            raw = os.environ.get(env_var) or cfg[key]
            return Path(os.path.expanduser(raw))

        return cls(
            hot_dir=resolve("hot_dir", "ENDOPHYND_HOT"),
            cold_dir=resolve("cold_dir", "ENDOPHYND_COLD"),
            db_dir=resolve("db_dir", "ENDOPHYND_DB"),
            hot_cap_gb=float(cfg.get("hot_cap_gb", 180)),
        )

    def hot(self, subdir: str = "") -> Path:
        """Return (and create) a subdirectory of hot_dir."""
        p = self.hot_dir / subdir if subdir else self.hot_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def cold(self, subdir: str = "") -> Path:
        p = self.cold_dir / subdir if subdir else self.cold_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def db(self, subdir: str = "") -> Path:
        p = self.db_dir / subdir if subdir else self.db_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def hot_usage_gb(self) -> float:
        """Return current hot cache usage in GB."""
        total = sum(
            f.stat().st_size
            for f in self.hot_dir.rglob("*")
            if f.is_file()
        )
        return total / (1024 ** 3)

    def ensure_hot_space(self, needed_gb: float = 1.0) -> None:
        """Raise if hot cache is too full to accept needed_gb more."""
        used = self.hot_usage_gb()
        available = self.hot_cap_gb - used
        if available < needed_gb:
            raise RuntimeError(
                f"Hot cache full: {used:.1f} GB used of {self.hot_cap_gb} GB cap; "
                f"need {needed_gb:.1f} GB more. "
                f"Free space on hot dir ({self.hot_dir}) or raise hot_cap_gb in cache.yml."
            )

    def delete_accession_transients(self, accession: str) -> list[Path]:
        """
        Delete all hot-cache files belonging to an accession.
        Returns the list of deleted paths (for logging).
        """
        deleted = []
        for f in self.hot_dir.rglob(f"{accession}.*"):
            if f.is_file():
                f.unlink()
                deleted.append(f)
        return deleted

    def init_dirs(self) -> None:
        """Create all cache directories if they don't exist."""
        for d in (self.hot_dir, self.cold_dir, self.db_dir):
            d.mkdir(parents=True, exist_ok=True)
