"""Fail-closed tests for the non-attesting Temporal start fingerprint."""
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app/shared/temporal_start_fingerprint.py"
spec = importlib.util.spec_from_file_location("temporal_start_fingerprint", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fingerprint_deterministic_and_not_an_attestation():
    a = module.start_request_digest("run-01", "DEMO", "acme", 0)
    assert len(a) == 64
    assert a == module.start_request_digest("run-01", "DEMO", "acme", 0)
    assert isinstance(module.canonical_start_request("run-01", "DEMO", "acme", 0), bytes)


@pytest.mark.parametrize("changed", [
    ("run-02", "DEMO", "acme", 0),
    ("run-01", "REPLAY", "acme", 0),
    ("run-01", "DEMO", "other", 0),
    ("run-01", "DEMO", "acme", 1),
])
def test_every_start_field_changes_digest(changed):
    assert module.start_request_digest(*changed) != module.start_request_digest(
        "run-01", "DEMO", "acme", 0)


@pytest.mark.parametrize("args", [
    ("../bad", "DEMO", "acme", 0),
    ("run-01", "DEMO", "é", 0),
    ("run-01", "UNKNOWN", "acme", 0),
    ("run-01", "DEMO", "acme", True),
    ("run-01", "DEMO", "acme", -1),
    ("run-01", "DEMO", "acme", 1.0),
    ("", "DEMO", "acme", 0),
    ("a" * 129, "DEMO", "acme", 0),
])
def test_invalid_start_requests_rejected(args):
    with pytest.raises(ValueError):
        module.start_request_digest(*args)
