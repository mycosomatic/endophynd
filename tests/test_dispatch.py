"""Tests for dispatch.py."""

import pytest

from endophynd.dispatch import Source, Platform, InputType, route_sample


def test_local_sample():
    row = {
        "sample_id": "FIXTURE_ITS",
        "source": "local",
        "accession": "tests/fixtures/mock_its_reads.fa",
        "platform": "synthetic",
        "input_type": "reads",
    }
    route = route_sample(row)
    assert route.source == Source.LOCAL
    assert route.platform == Platform.SYNTHETIC
    assert route.input_type == InputType.READS
    assert route.local_path == "tests/fixtures/mock_its_reads.fa"
    assert route.accession is None


def test_local_streaming_command():
    row = {
        "sample_id": "X",
        "source": "local",
        "accession": "input.fa",
        "platform": "illumina",
        "input_type": "reads",
    }
    route = route_sample(row)
    cmd = route.streaming_command("out.fa", "seeds.fa", k=31, hdist=1)
    assert "bbduk.sh" in cmd
    assert "input.fa" in cmd


def test_logan_not_yet_implemented():
    row = {
        "sample_id": "GBI001",
        "source": "logan",
        "accession": "GCA_000001405",
        "platform": "illumina",
        "input_type": "unitigs",
    }
    route = route_sample(row)
    with pytest.raises(NotImplementedError, match="Phase 1"):
        route.streaming_command("out.fa", "seeds.fa", k=31, hdist=1)


def test_unknown_platform_defaults():
    row = {
        "sample_id": "X",
        "source": "local",
        "accession": "f.fa",
        "platform": "totally_unknown",
        "input_type": "reads",
    }
    route = route_sample(row)
    assert route.platform == Platform.UNKNOWN
