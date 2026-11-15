"""Offline correlation regression. No network or production systems."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import InvalidEvent, correlate_events, normalize_event

NOW = "2026-11-15T12:00:00Z"


def event(**overrides):
    value = dict(tenant_id="acme", source="checkmk", source_event_id="san-1",
                 ci_id="san-01", service_id="payments", severity="P1",
                 evidence_sha256="a" * 64, observed_at="2026-11-15T11:59:00Z",
                 known_at="2026-11-15T11:59:05Z")
    value.update(overrides)
    return value


def test_dedupe_and_deterministic_replay():
    a = event()
    b = event(source="prometheus", source_event_id="pay-2", severity="P2")
    result = correlate_events([a, b, copy.deepcopy(a)], as_of=NOW)
    assert result == correlate_events([b, a, a], as_of=NOW)
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["event_count"] == 2
    assert result["incidents"][0]["priority"] == "P1"
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_cross_tenant_isolation():
    result = correlate_events([event(), event(tenant_id="other")], as_of=NOW)
    assert len(result["incidents"]) == 2
    assert len({x["incident_id"] for x in result["incidents"]}) == 2


def test_cross_service_isolation():
    result = correlate_events([event(), event(service_id="storage")], as_of=NOW)
    assert len(result["incidents"]) == 2


def test_conflicting_duplicate_rejected_without_overwrite():
    result = correlate_events([event(), event(ci_id="other-ci")], as_of=NOW)
    assert result["incidents"] == []
    assert result["rejected"] == [{"index": 1, "reason": "conflicting duplicate event identity"}]
    reversed_result = correlate_events([event(ci_id="other-ci"), event()], as_of=NOW)
    assert reversed_result["incidents"] == []
    assert reversed_result["rejected"] == [{"index": 1, "reason": "conflicting duplicate event identity"}]


@pytest.mark.parametrize("override", [
    {"tenant_id": ""}, {"source": "unknown"}, {"source_event_id": None},
    {"ci_id": ""}, {"service_id": None}, {"severity": "P0"},
    {"evidence_sha256": "invalid"}, {"observed_at": "bad"},
    {"observed_at": "2026-11-15T11:59:00"},
    {"known_at": "2026-11-15T11:58:00Z"},
])
def test_invalid_event_fails_closed(override):
    with pytest.raises(InvalidEvent):
        normalize_event(event(**override))


def test_stale_future_and_not_yet_known_are_rejected():
    result = correlate_events([
        event(observed_at="2026-11-15T11:00:00Z"),
        event(source_event_id="future", observed_at="2026-11-15T12:01:00Z",
              known_at="2026-11-15T12:01:01Z"),
        event(source_event_id="unknown-yet", known_at="2026-11-15T12:01:00Z"),
    ], as_of=NOW)
    assert result["incidents"] == []
    assert len(result["rejected"]) == 3


def test_invalid_container_and_age():
    with pytest.raises(InvalidEvent):
        correlate_events({}, as_of=NOW)
    with pytest.raises(InvalidEvent):
        correlate_events([], as_of=NOW, max_age_seconds=True)


def test_no_mutation_of_input():
    raw = event()
    original = copy.deepcopy(raw)
    correlate_events([raw], as_of=NOW)
    assert raw == original
