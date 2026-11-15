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


@pytest.mark.parametrize("field", ["from_id", "to_id", "source_id"])
def test_oversized_twin_edge_identity_rejected(field):
    result = resolve_impact(incident(), [edge("san-01", "payments", **{field: "x" * 257})], as_of=NOW)
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
    assert result["rejected_edges"][0]["reason"] == "oversized edge identity"
    assert result["live_remediation_authorized"] is False


@pytest.mark.parametrize("field", ["from_id", "to_id", "source_id"])
def test_twin_edge_identity_boundary_accepted(field):
    e = edge("san-01", "payments", **{field: "x" * 256})
    result = resolve_impact(incident(), [e], as_of=NOW)
    assert result["rejected_edges"] == []
    assert result["live_remediation_authorized"] is False



def test_twin_rejects_more_than_100_sourced_paths_without_partial_proofs():
    graph = [edge("san-01", f"hop-{i}") for i in range(101)]
    graph += [edge(f"hop-{i}", "payments") for i in range(101)]
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is True
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []
    assert result["live_remediation_authorized"] is False


def test_twin_accepts_exactly_100_sourced_paths():
    graph = [edge("san-01", f"hop-{i}") for i in range(100)]
    graph += [edge(f"hop-{i}", "payments") for i in range(100)]
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is False
    assert len(result["paths"]) == 100
    assert result["impact_state"] == "SOURCED_SYNTHETIC_PATH"


def test_twin_rejects_path_depth_above_100_without_partial_proofs():
    nodes = ["san-01"] + [f"hop-{i}" for i in range(99)] + ["payments"]
    graph = [edge(src, dst) for src, dst in zip(nodes, nodes[1:])]
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is True
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []



def test_twin_accepts_path_depth_at_100_node_boundary():
    nodes = ["san-01"] + [f"hop-{i}" for i in range(98)] + ["payments"]
    graph = [edge(src, dst) for src, dst in zip(nodes, nodes[1:])]
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is False
    assert result["impact_state"] == "SOURCED_SYNTHETIC_PATH"
    assert result["paths"][0]["nodes"] == nodes
    assert result["live_remediation_authorized"] is False



def test_twin_depth_boundary_ignores_cycle_only_outgoing_edges():
    nodes = ["san-01"] + [f"hop-{i}" for i in range(99)]
    graph = [edge(src, dst) for src, dst in zip(nodes, nodes[1:])]
    graph.append(edge(nodes[-1], nodes[0]))
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is False
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []


def test_twin_depth_boundary_exhausts_on_unvisited_neighbor():
    nodes = ["san-01"] + [f"hop-{i}" for i in range(99)]
    graph = [edge(src, dst) for src, dst in zip(nodes, nodes[1:])]
    graph.extend([edge(nodes[-1], nodes[0]), edge(nodes[-1], "new-hop")])
    result = resolve_impact(incident(), graph, as_of=NOW)
    assert result["resource_budget_exhausted"] is True
    assert result["impact_state"] == "UNKNOWN"
    assert result["paths"] == []


@pytest.mark.parametrize("field", ["tenant_id", "service_id"])
def test_twin_rejects_oversized_incident_identity(field):
    sample = incident()
    sample[field] = "x" * 257
    with pytest.raises(InvalidEvent, match="invalid incident identity"):
        resolve_impact(sample, [], as_of=NOW)


def test_twin_rejects_oversized_incident_ci():
    sample = incident()
    sample["events"][0]["ci_id"] = "x" * 257
    with pytest.raises(InvalidEvent, match="invalid incident CI"):
        resolve_impact(sample, [], as_of=NOW)


@pytest.mark.parametrize("incident_id", [None, "", "x" * 257, 42])
def test_twin_rejects_invalid_incident_id(incident_id):
    sample = incident()
    sample["incident_id"] = incident_id
    with pytest.raises(InvalidEvent, match="invalid incident id"):
        resolve_impact(sample, [edge("san-01", "payments")], as_of=NOW)


def test_twin_rejects_event_service_mismatch():
    sample = incident()
    sample["events"][0]["service_id"] = "other-service"
    with pytest.raises(InvalidEvent, match="cross-tenant or invalid incident event"):
        resolve_impact(sample, [edge("san-01", "payments")], as_of=NOW)
