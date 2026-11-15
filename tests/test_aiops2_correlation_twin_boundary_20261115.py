"""Additional isolated regression gates for synthetic correlation and Twin impact.

All inputs are fabricated. No adapters, sockets, databases or host access.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact

NOW = "2026-11-15T12:00:00Z"


def signal(source, event_id, *, tenant="acme", ci="san-01", service="payments"):
    return {
        "tenant_id": tenant, "source": source, "source_event_id": event_id,
        "ci_id": ci, "service_id": service, "severity": "P2",
        "evidence_sha256": "a" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }


def test_three_source_identities_remain_distinct_and_unattested():
    signals = [signal(s, "same-upstream-id") for s in ("checkmk", "prometheus", "grafana")]
    snapshot = copy.deepcopy(signals)
    result = correlate_events(signals, as_of=NOW)
    assert signals == snapshot
    assert result["schema"] == "aiops2.synthetic-event-correlation.v1"
    assert result["rejected"] == []
    assert len(result["incidents"]) == 1
    assert result["incidents"][0]["event_count"] == 3
    assert {e["source"] for e in result["incidents"][0]["events"]} == {"checkmk", "prometheus", "grafana"}
    assert result["incidents"][0]["impact_state"] == "UNKNOWN"
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_duplicate_identity_conflict_never_selects_a_winner():
    original = signal("checkmk", "same")
    conflicting = {**original, "evidence_sha256": "b" * 64}
    for ordering in ([original, conflicting], [conflicting, original]):
        result = correlate_events(ordering, as_of=NOW)
        assert result["incidents"] == []
        assert result["rejected"][0]["reason"] == "conflicting duplicate event identity"


def test_missing_cmdb_edges_cannot_infer_san_storage_payments():
    incident = correlate_events([signal("checkmk", "san-alert")], as_of=NOW)["incidents"][0]
    result = resolve_impact(incident, [], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_other_tenant_cmdb_edge_cannot_prove_payments():
    incident = correlate_events([signal("prometheus", "san-alert")], as_of=NOW)["incidents"][0]
    edge = {
        "tenant_id": "other", "from_id": "san-01", "to_id": "payments",
        "source_id": "fixture-glpi", "evidence_sha256": "c" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
    }
    result = resolve_impact(incident, [edge], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
    assert result["rejected_edges"] == [{"index": 0, "reason": "tenant mismatch"}]
