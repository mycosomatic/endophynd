"""Tests for cache.py."""

import os
import tempfile
from pathlib import Path

import pytest

from endophynd.cache import CacheManager


@pytest.fixture
def tmp_cache(tmp_path):
    return CacheManager(
        hot_dir=tmp_path / "hot",
        cold_dir=tmp_path / "cold",
        db_dir=tmp_path / "db",
        hot_cap_gb=10.0,
    )


def test_init_creates_dirs(tmp_cache):
    tmp_cache.init_dirs()
    assert tmp_cache.hot_dir.exists()
    assert tmp_cache.cold_dir.exists()
    assert tmp_cache.db_dir.exists()


def test_hot_creates_subdir(tmp_cache):
    tmp_cache.init_dirs()
    p = tmp_cache.hot("baited")
    assert p.exists()
    assert p == tmp_cache.hot_dir / "baited"


def test_hot_usage_empty(tmp_cache):
    tmp_cache.init_dirs()
    assert tmp_cache.hot_usage_gb() == 0.0


def test_hot_usage_with_file(tmp_cache):
    tmp_cache.init_dirs()
    (tmp_cache.hot_dir / "test.fa").write_bytes(b"A" * 1024)
    usage = tmp_cache.hot_usage_gb()
    assert usage > 0.0
    assert usage < 1.0


def test_ensure_hot_space_passes(tmp_cache):
    tmp_cache.init_dirs()
    tmp_cache.ensure_hot_space(needed_gb=1.0)  # should not raise


def test_ensure_hot_space_fails(tmp_cache):
    tmp_cache.init_dirs()
    with pytest.raises(RuntimeError, match="Hot cache full"):
        tmp_cache.ensure_hot_space(needed_gb=100.0)  # way over the 10 GB cap


def test_delete_accession_transients(tmp_cache):
    tmp_cache.init_dirs()
    f1 = tmp_cache.hot_dir / "ACC001.baited.fa"
    f2 = tmp_cache.hot_dir / "ACC001.gated.fa"
    f3 = tmp_cache.hot_dir / "ACC002.baited.fa"
    f1.write_text("x")
    f2.write_text("x")
    f3.write_text("x")

    deleted = tmp_cache.delete_accession_transients("ACC001")
    assert len(deleted) == 2
    assert not f1.exists()
    assert not f2.exists()
    assert f3.exists()


def test_from_config(tmp_path):
    import yaml

    config = {
        "hot_dir": str(tmp_path / "hot"),
        "cold_dir": str(tmp_path / "cold"),
        "db_dir": str(tmp_path / "db"),
        "hot_cap_gb": 50.0,
    }
    config_path = tmp_path / "cache.yml"
    config_path.write_text(yaml.dump(config))

    cache = CacheManager.from_config(config_path)
    assert cache.hot_cap_gb == 50.0
    assert cache.hot_dir == tmp_path / "hot"
