"""Contract tests for the offline SAN -> Payments vertical slice."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_noc_decision import build_noc_decision

NOW = "2026-11-15T12:00:00Z"


def event(tenant="acme", source="checkmk", ident="san-1", ci="san-01", severity="P1"):
    return {"tenant_id": tenant, "source": source, "source_event_id": ident,
            "ci_id": ci, "service_id": "payments", "severity": severity,
            "evidence_sha256": "a" * 64,
            "observed_at": "2026-11-15T11:59:00Z",
            "known_at": "2026-11-15T11:59:05Z"}


def edge(src, dst, tenant="acme"):
    return {"tenant_id": tenant, "from_id": src, "to_id": dst,
            "source_id": "synthetic-cmdb", "evidence_sha256": "b" * 64,
            "observed_at": "2026-11-15T11:59:00Z"}


def test_end_to_end_san_payments_computed_projection():
    events = [event(), event(source="prometheus", ident="payments-2",
                             ci="payments-api", severity="P2"), event()]
    edges = [edge("san-01", "storage"), edge("storage", "payments")]
    result = build_noc_decision(events, edges, as_of=NOW)
    assert result["mode"] == "SIMULATION"
    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision["event_count"] == 2
    assert decision["priority"] == "P1"
    assert decision["impact_state"] == "SOURCED_SYNTHETIC_PATH"
    assert decision["impact_paths"][0]["nodes"] == ["san-01", "storage", "payments"]
    assert decision["critic"]["root_cause_confirmed"] is False
    assert decision["policy_disposition"] == "DENY_LIVE"
    assert decision["next_noc_action"] == "REVIEW_SYNTHETIC_EVIDENCE"
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False
    json.dumps(result)


def test_missing_twin_dependency_requires_evidence():
    result = build_noc_decision([event()], [], as_of=NOW)
    decision = result["decisions"][0]
    assert decision["impact_state"] == "UNKNOWN"
    assert decision["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert decision["next_noc_action"] == "COLLECT_MISSING_DEPENDENCY_EVIDENCE"


def test_cross_tenant_edges_cannot_prove_impact():
    result = build_noc_decision([event()], [edge("san-01", "payments", tenant="other")], as_of=NOW)
    assert result["decisions"][0]["impact_state"] == "UNKNOWN"
    assert result["decisions"][0]["rejected_edges"][0]["reason"] == "tenant mismatch"


def test_two_tenants_stay_separate():
    result = build_noc_decision([event(), event(tenant="other")],
                                [edge("san-01", "payments")], as_of=NOW)
    assert len(result["decisions"]) == 2
    states = {x["tenant_id"]: x["impact_state"] for x in result["decisions"]}
    assert states == {"acme": "SOURCED_SYNTHETIC_PATH", "other": "UNKNOWN"}


def test_deterministic_replay_no_input_mutation():
    events = [event(), event(source="grafana", ident="g-1")]
    edges = [edge("san-01", "payments")]
    original_events, original_edges = copy.deepcopy(events), copy.deepcopy(edges)
    assert build_noc_decision(events, edges, as_of=NOW) == build_noc_decision(
        list(reversed(events)), list(reversed(edges)), as_of=NOW)
    assert events == original_events and edges == original_edges


def test_stale_event_does_not_enter_decision():
    stale = event()
    stale["observed_at"] = "2026-11-15T10:00:00Z"
    result = build_noc_decision([stale], [edge("san-01", "payments")], as_of=NOW)
    assert result["decisions"] == []
    assert len(result["rejected_events"]) == 1



def test_conflicting_source_identity_cannot_create_noc_decision():
    first = event()
    conflicting = event(ci="different-ci")
    for receipts in ([first, conflicting], [conflicting, first]):
        result = build_noc_decision(receipts, [edge("san-01", "payments")], as_of=NOW)
        assert result["decisions"] == []
        assert any("conflicting duplicate event identity" in rejected["reason"]
                   for rejected in result["rejected_events"])
        assert result["live_remediation_authorized"] is False


def test_one_tenant_conflict_does_not_discard_other_tenant_incident():
    first = event()
    conflicting = event(ci="different-ci")
    independent = event(tenant="other")
    result = build_noc_decision(
        [first, independent, conflicting],
        [edge("san-01", "payments", tenant="other")],
        as_of=NOW,
    )
    assert len(result["decisions"]) == 1
    assert result["decisions"][0]["tenant_id"] == "other"
    assert result["decisions"][0]["impact_state"] == "SOURCED_SYNTHETIC_PATH"
    assert result["decisions"][0]["policy_disposition"] == "DENY_LIVE"



def test_high_fanout_twin_budget_exhaustion_never_promotes_impact():
    # The Twin's fixed path-state budget is exhausted by a synthetic fanout.
    # Even if a dependency path exists, partial traversal cannot prove impact.
    edges = [edge("san-01", f"node-{i:05d}") for i in range(10001)]
    edges.append(edge("san-01", "payments"))
    result = build_noc_decision([event()], edges, as_of=NOW)
    decision = result["decisions"][0]
    assert decision["impact_state"] == "UNKNOWN"
    assert decision["impact_paths"] == []
    assert decision["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert decision["next_noc_action"] == "COLLECT_MISSING_DEPENDENCY_EVIDENCE"
    assert decision["policy_disposition"] == "DENY_LIVE"
    assert decision["runtime_attested"] is False
    assert decision["live_remediation_authorized"] is False



def test_oversized_twin_edge_never_promotes_end_to_end_impact():
    oversized = edge("san-01", "payments")
    oversized["source_id"] = "synthetic-" + "x" * 257
    result = build_noc_decision([event()], [oversized], as_of=NOW)
    decision = result["decisions"][0]
    assert decision["impact_state"] == "UNKNOWN"
    assert decision["impact_paths"] == []
    assert decision["rejected_edges"][0]["reason"] == "oversized edge identity"
    assert decision["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert decision["policy_disposition"] == "DENY_LIVE"
    assert decision["live_remediation_authorized"] is False


def test_oversized_event_identity_never_creates_end_to_end_decision():
    oversized = event()
    oversized["ci_id"] = "x" * 257
    result = build_noc_decision([oversized], [edge("san-01", "payments")], as_of=NOW)
    assert result["decisions"] == []
    assert len(result["rejected_events"]) == 1
    assert result["live_remediation_authorized"] is False



def test_decision_projects_deduplicated_incident_ci_origins():
    receipts = [event(), event(source="prometheus", ident="p-2", ci="payments-api"),
                event(source="grafana", ident="g-3", ci="san-01")]
    result = build_noc_decision(receipts, [edge("san-01", "payments")], as_of=NOW)
    decision = result["decisions"][0]
    assert decision["incident_ci_ids"] == ["payments-api", "san-01"]
    assert decision["impact_paths"][0]["nodes"][0] in decision["incident_ci_ids"]
    assert decision["policy_disposition"] == "DENY_LIVE"


def test_unknown_decision_still_projects_incident_ci_origins():
    result = build_noc_decision([event()], [], as_of=NOW)
    decision = result["decisions"][0]
    assert decision["incident_ci_ids"] == ["san-01"]
    assert decision["impact_paths"] == []
    assert decision["live_remediation_authorized"] is False
