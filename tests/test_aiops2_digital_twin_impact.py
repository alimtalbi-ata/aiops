"""Isolated sourced Digital Twin impact tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_digital_twin_impact import resolve_impact
from aiops2_event_correlation import InvalidEvent

NOW = "2026-11-15T12:00:00Z"


def incident(tenant="acme"):
    return {"incident_id": "SYN-1", "tenant_id": tenant, "service_id": "payments",
            "events": [{"tenant_id": tenant, "ci_id": "san-01"}]}


def edge(src, dst, **kw):
    e = {"tenant_id": "acme", "from_id": src, "to_id": dst,
         "source_id": "cmdb-synthetic", "evidence_sha256": "a" * 64,
         "observed_at": "2026-11-15T11:00:00Z"}
    e.update(kw)
    return e


def test_sourced_multi_hop_path_and_no_live_claim():
    result = resolve_impact(incident(), [edge("san-01", "storage"),
                                           edge("storage", "payments")], as_of=NOW)
    assert result["impact_state"] == "SOURCED_SYNTHETIC_PATH"
    assert result["paths"][0]["nodes"] == ["san-01", "storage", "payments"]
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


def test_missing_edge_unknown():
    result = resolve_impact(incident(), [edge("san-01", "storage")], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []


def test_cross_tenant_edge_rejected():
    result = resolve_impact(incident(), [edge("san-01", "payments", tenant_id="other")], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert result["rejected_edges"][0]["reason"] == "tenant mismatch"


@pytest.mark.parametrize("change", [
    {"observed_at": "2026-11-13T11:00:00Z"},
    {"observed_at": "2026-11-15T13:00:00Z"},
    {"observed_at": "2026-11-15T11:00:00"},
    {"evidence_sha256": "forged"},
    {"source_id": ""},
])
def test_invalid_or_stale_edge_cannot_create_impact(change):
    result = resolve_impact(incident(), [edge("san-01", "payments", **change)], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert len(result["rejected_edges"]) == 1


def test_cycles_do_not_loop():
    result = resolve_impact(incident(), [edge("san-01", "storage"),
                                           edge("storage", "san-01"),
                                           edge("storage", "payments")], as_of=NOW)
    assert len(result["paths"]) == 1


def test_invalid_incident_cross_tenant_fails_closed():
    with pytest.raises(InvalidEvent):
        resolve_impact({"tenant_id": "acme", "service_id": "payments",
                        "events": [{"tenant_id": "other", "ci_id": "san-01"}]}, [], as_of=NOW)



def test_path_budget_exhaustion_fails_closed_without_partial_proofs():
    graph = [edge("san-01", "storage"), edge("storage", "payments")]
    result = resolve_impact(incident(), graph, as_of=NOW, max_path_expansions=1)
    assert result["resource_budget_exhausted"] is True
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
    assert result["live_remediation_authorized"] is False


def test_path_budget_sufficient_for_sourced_path():
    graph = [edge("san-01", "storage"), edge("storage", "payments")]
    result = resolve_impact(incident(), graph, as_of=NOW, max_path_expansions=3)
    assert result["resource_budget_exhausted"] is False
    assert result["impact_state"] == "SOURCED_SYNTHETIC_PATH"


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_path_budget_rejected(budget):
    with pytest.raises(InvalidEvent):
        resolve_impact(incident(), [], as_of=NOW, max_path_expansions=budget)



def test_high_fanout_cannot_overfill_path_queue():
    graph = [edge("san-01", f"branch-{i}") for i in range(50)]
    graph.append(edge("branch-0", "payments"))
    result = resolve_impact(incident(), graph, as_of=NOW, max_path_expansions=5)
    assert result["resource_budget_exhausted"] is True
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
