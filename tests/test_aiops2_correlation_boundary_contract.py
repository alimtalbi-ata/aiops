"""Offline boundary contracts for deterministic synthetic correlation only.

No external systems, LIVE claims, or Policy/HITL authority.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events

NOW = "2026-11-15T12:00:00Z"


def receipt(**changes):
    row = {
        "tenant_id": "acme", "source": "checkmk",
        "source_event_id": "san-1", "ci_id": "san-01",
        "service_id": "payments", "severity": "P2",
        "evidence_sha256": "a" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }
    row.update(changes)
    return row


def test_exact_freshness_boundary_is_inclusive_and_next_second_rejected():
    rows = [
        receipt(source_event_id="boundary", observed_at="2026-11-15T11:45:00Z",
                known_at="2026-11-15T11:45:00Z"),
        receipt(source_event_id="stale", observed_at="2026-11-15T11:44:59Z",
                known_at="2026-11-15T11:44:59Z"),
    ]
    result = correlate_events(rows, as_of=NOW, max_age_seconds=900)
    assert [x["source_event_id"] for x in result["incidents"][0]["events"]] == ["boundary"]
    assert result["rejected"] == [{"index": 1, "reason": "event outside freshness window"}]
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False


def test_equivalent_timezone_receipts_deduplicate_by_normalized_identity():
    a = receipt()
    b = receipt(observed_at="2026-11-15T12:59:00+01:00",
                known_at="2026-11-15T12:59:05+01:00")
    result = correlate_events([a, b], as_of=NOW)
    assert result["rejected"] == []
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["event_count"] == 1
    assert result["runtime_attested"] is False


def test_conflicting_evidence_digest_invalidates_both_receipts():
    a = receipt()
    b = receipt(evidence_sha256="b" * 64)
    result = correlate_events([a, b], as_of=NOW)
    assert result["incidents"] == []
    assert result["rejected"] == [
        {"index": 0, "reason": "conflicting duplicate event identity"},
        {"index": 1, "reason": "conflicting duplicate event identity"},
    ]
    assert result["live_remediation_authorized"] is False
