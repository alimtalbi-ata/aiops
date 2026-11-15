"""Offline, adversarial contract tests for synthetic correlation (no LIVE effects)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events

NOW = "2026-11-15T12:00:00Z"


def sample(source="checkmk", source_event_id="san-1", **changes):
    row = {
        "tenant_id": "acme", "source": source, "source_event_id": source_event_id,
        "ci_id": "san-01", "service_id": "payments", "severity": "P2",
        "evidence_sha256": "a" * 64, "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }
    row.update(changes)
    return row


def test_three_source_provenance_and_no_inferred_san_payments_causality():
    rows = [sample("checkmk", "san-1", severity="P1"),
            sample("prometheus", "pay-1", evidence_sha256="b" * 64),
            sample("grafana", "dashboard-1", evidence_sha256="c" * 64)]
    original = copy.deepcopy(rows)
    result = correlate_events(rows + [copy.deepcopy(rows[0])], as_of=NOW)
    incident, = result["incidents"]
    assert incident["event_count"] == 3
    assert incident["priority"] == "P1"
    assert {(x["source"], x["source_event_id"], x["evidence_sha256"]) for x in incident["events"]} == {
        ("checkmk", "san-1", "a" * 64),
        ("prometheus", "pay-1", "b" * 64),
        ("grafana", "dashboard-1", "c" * 64),
    }
    assert incident["impact_state"] == "UNKNOWN"
    assert incident["runtime_attested"] is False
    assert incident["live_remediation_authorized"] is False
    assert result["scope"] == "ISOLATED_DETERMINISTIC_NO_LIVE_EFFECTS"
    assert rows == original
    # Shared service grouping is not proof of a Twin dependency or a causal edge.
    assert "causal_link" not in incident
    assert "twin_edge" not in incident


def test_event_identity_is_tenant_and_source_scoped():
    rows = [sample(), sample("prometheus", "san-1"),
            sample(tenant_id="other", evidence_sha256="d" * 64)]
    result = correlate_events(rows, as_of=NOW)
    assert len(result["incidents"]) == 2
    assert sorted(x["event_count"] for x in result["incidents"]) == [1, 2]
    assert not result["rejected"]


def test_conflicting_provenance_invalidates_identity_in_any_order():
    a = sample()
    b = sample(evidence_sha256="f" * 64)
    for rows in ([a, b], [b, a]):
        result = correlate_events(rows, as_of=NOW)
        assert result["incidents"] == []
        assert result["rejected"][0]["reason"] == "conflicting duplicate event identity"
        assert result["live_remediation_authorized"] is False


def test_freshness_boundary_and_unknown_no_policy_bypass():
    boundary = sample(observed_at="2026-11-15T11:45:00Z")
    expired = sample(source_event_id="old", observed_at="2026-11-15T11:44:59Z")
    future_knowledge = sample(source_event_id="unseen", known_at="2026-11-15T12:00:01Z")
    result = correlate_events([boundary, expired, future_knowledge], as_of=NOW)
    assert result["incidents"][0]["event_count"] == 1
    assert [x["index"] for x in result["rejected"]] == [1, 2]
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False


def test_invalid_tenant_source_and_provenance_are_rejected_fail_closed():
    cases = [
        sample(tenant_id=""),
        sample(source="unknown-monitor"),
        sample(evidence_sha256="not-a-sha256"),
        sample(known_at="2026-11-15T11:58:00Z"),
        sample(observed_at="2026-11-15T11:59:00"),
    ]
    result = correlate_events(cases, as_of=NOW)
    assert result["incidents"] == []
    assert [item["index"] for item in result["rejected"]] == list(range(len(cases)))
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_tenant_boundaries_do_not_merge_same_service_or_source_event_id():
    result = correlate_events([
        sample(tenant_id="acme", severity="P1"),
        sample(tenant_id="another", severity="P4", evidence_sha256="b" * 64),
    ], as_of=NOW)
    assert len(result["incidents"]) == 2
    assert {incident["tenant_id"] for incident in result["incidents"]} == {"acme", "another"}
    assert all(incident["event_count"] == 1 for incident in result["incidents"])
    assert all(incident["impact_state"] == "UNKNOWN" for incident in result["incidents"])
    assert all(incident["live_remediation_authorized"] is False for incident in result["incidents"])
