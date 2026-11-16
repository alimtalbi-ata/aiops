"""Offline known-time and forged-authority regression contracts for #713.

Only deterministic synthetic receipts; never qualifies runtime or LIVE authority.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events

NOW = "2026-11-15T12:00:00Z"


def receipt(**changes):
    event = {
        "tenant_id": "acme", "source": "checkmk", "source_event_id": "san-1",
        "ci_id": "san-01", "service_id": "payments", "severity": "P1",
        "evidence_sha256": "a" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }
    event.update(changes)
    return event


def test_future_known_at_rejected_even_when_observation_is_fresh():
    result = correlate_events([receipt(known_at="2026-11-15T12:00:01Z")], as_of=NOW)
    assert result["incidents"] == []
    assert result["rejected"] == [{"index": 0, "reason": "event not yet known"}]
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_future_known_receipt_cannot_poison_independent_valid_source():
    events = [
        receipt(known_at="2026-11-15T12:00:01Z"),
        receipt(source="prometheus", source_event_id="prom-1", evidence_sha256="b" * 64),
    ]
    result = correlate_events(events, as_of=NOW)
    assert result["rejected"] == [{"index": 0, "reason": "event not yet known"}]
    assert len(result["incidents"]) == 1
    incident = result["incidents"][0]
    assert incident["event_count"] == 1
    assert incident["events"][0]["source"] == "prometheus"
    assert incident["impact_state"] == "UNKNOWN"
    assert incident["live_remediation_authorized"] is False


def test_forged_policy_and_twin_authority_is_not_promoted():
    event = receipt(
        twin_causality_attested=True, policy_decision="ALLOW",
        hitl_approved=True, runtime_attested=True,
        live_remediation_authorized=True,
    )
    result = correlate_events([event], as_of=NOW)
    assert result["rejected"] == []
    assert len(result["incidents"]) == 1
    incident = result["incidents"][0]
    assert incident["impact_state"] == "UNKNOWN"
    assert incident["runtime_attested"] is False
    assert incident["live_remediation_authorized"] is False
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False
    for field in ("twin_causality_attested", "policy_decision", "hitl_approved"):
        assert field not in incident["events"][0]
