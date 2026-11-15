"""Isolated synthetic fixture tests: no network, SQL, host or LIVE effects."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_twin_dependency_read import project_dependencies

NOW = "2026-11-15T12:00:00Z"
NODES = [
    {"id": "san-a", "kind": "SAN", "tenant_id": "acme"},
    {"id": "disk-a", "kind": "STORAGE", "tenant_id": "acme"},
    {"id": "payments", "kind": "SERVICE", "tenant_id": "acme"},
]


def edge(a, b, **changes):
    value = {"from": a, "to": b, "tenant_id": "acme",
             "authority": "GLPI_CMDB", "source_ref": "fixture:cmdb:42",
             "observed_at": "2026-11-15T11:59:00Z", "attested": True}
    value.update(changes)
    return value


def project(edges, nodes=NODES):
    return project_dependencies(nodes, edges, tenant_id="acme", as_of=NOW)


def test_synthetic_san_storage_payments_is_sourced_but_not_live():
    result = project([edge("san-a", "disk-a"), edge("disk-a", "payments")])
    assert [e["state"] for e in result["edges"]] == ["SOURCED", "SOURCED"]
    assert result["mode"] == "DEMO_FIXTURE"
    assert result["runtime_attested"] is False
    assert result["live_remediation_authorized"] is False


@pytest.mark.parametrize("changes", [
    {"source_ref": ""}, {"attested": False}, {"attested": "true"},
    {"authority": "TWIN"}, {"observed_at": "2026-11-15T11:00:00Z"},
    {"observed_at": "2026-11-15T12:01:00Z"},
    {"observed_at": "not-a-date"},
])
def test_unproven_edge_is_unknown(changes):
    assert project([edge("san-a", "disk-a", **changes)])["edges"][0]["state"] == "UNKNOWN"


def test_invalid_direction_unknown():
    assert project([edge("payments", "san-a")])["edges"][0]["state"] == "UNKNOWN"


def test_cross_tenant_and_missing_endpoint_rejected():
    with pytest.raises(ValueError):
        project([edge("san-a", "disk-a", tenant_id="other")])
    with pytest.raises(ValueError):
        project([edge("san-a", "missing")])
    with pytest.raises(ValueError):
        project([], NODES + [{"id": "foreign", "kind": "SAN", "tenant_id": "other"}])


def test_duplicate_and_ambiguous_contract_rejected():
    with pytest.raises(ValueError):
        project([edge("san-a", "disk-a")] * 2)
    with pytest.raises(ValueError):
        project([dict(edge("san-a", "disk-a"), arbitrary="query")])
    with pytest.raises(ValueError):
        project([], NODES + [NODES[0]])
