"""Offline source-namespace and tenant isolation regressions for #713.

Synthetic fixtures only: no network, runtime proof, or authorization.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events

NOW = "2026-11-15T12:00:00Z"


def receipt(*, tenant="acme", source="checkmk", digest="a" * 64, ci="san-01"):
    return {
        "tenant_id": tenant,
        "source": source,
        "source_event_id": "shared-id",
        "ci_id": ci,
        "service_id": "payments",
        "severity": "P1",
        "evidence_sha256": digest,
        "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }


def test_same_source_event_id_from_independent_sources_is_not_a_conflict():
    result = correlate_events(
        [receipt(source="checkmk"), receipt(source="prometheus", digest="b" * 64)],
        as_of=NOW,
    )
    assert result["rejected"] == []
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["event_count"] == 2
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_same_source_and_event_id_across_tenants_keeps_evidence_separate():
    result = correlate_events(
        [receipt(tenant="acme"), receipt(tenant="other", digest="b" * 64)],
        as_of=NOW,
    )
    assert result["rejected"] == []
    assert len(result["incidents"]) == 2
    assert {x["tenant_id"] for x in result["incidents"]} == {"acme", "other"}
    assert len({x["incident_id"] for x in result["incidents"]}) == 2
    assert all(x["event_count"] == 1 for x in result["incidents"])
    assert all(x["impact_state"] == "UNKNOWN" for x in result["incidents"])


def test_conflict_in_one_tenant_cannot_invalidate_another_tenant():
    events = [
        receipt(tenant="acme"),
        receipt(tenant="other", digest="b" * 64),
        receipt(tenant="acme", digest="c" * 64, ci="san-02"),
    ]
    result = correlate_events(events, as_of=NOW)
    assert result["rejected"] == [
        {"index": 0, "reason": "conflicting duplicate event identity"},
        {"index": 2, "reason": "conflicting duplicate event identity"},
    ]
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["tenant_id"] == "other"
    assert result["incidents"][0]["event_count"] == 1
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False
