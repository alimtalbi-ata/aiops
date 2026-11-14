"""Offline negative qualification for Temporal start-input comparison."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.temporal_start_comparison import compare_temporal_start_input

BASE = {"run_id": "run-01", "mode": "DEMO", "scenario_id": "acme", "version": 0}


def test_exact_tuple_matches_without_granting_authority():
    assert compare_temporal_start_input(BASE, dict(BASE)) == "MATCH"


@pytest.mark.parametrize("key,value", [
    ("run_id", "run-02"), ("mode", "LIVE"),
    ("scenario_id", "other"), ("version", 1),
])
def test_any_difference_is_mismatch(key, value):
    changed = dict(BASE, **{key: value})
    assert compare_temporal_start_input(BASE, changed) == "MISMATCH"


@pytest.mark.parametrize("untrusted", [
    None, [], "run-01", {}, {"run_id": "run-01"},
    dict(BASE, version=True), dict(BASE, version="0"),
    dict(BASE, extra="forged"), dict(BASE, scenario_id="../bad"),
])
def test_missing_or_malformed_input_never_matches(untrusted):
    assert compare_temporal_start_input(BASE, untrusted) == "UNKNOWN"


def test_invalid_core_request_never_matches():
    assert compare_temporal_start_input(dict(BASE, version=True), BASE) == "UNKNOWN"
