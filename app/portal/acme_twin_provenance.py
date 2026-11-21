"""Additive STORY_OFFLINE projection. No I/O, clock, backend or authority."""
from __future__ import annotations

import hashlib
from typing import Any

from portal.acme_fixture_contract import load_fixture_bytes, validate_fixture

SCHEMA = "aiops.acme.twin-provenance.v1"
SOURCE_PATH = "app/portal/acme-fixtures.json"


def build_twin_evidence(raw: bytes) -> dict[str, Any]:
    """Validate the very bytes used for evidence; never infer runtime health.

    Git source SHA stays null: this function cannot attest checkout identity.
    IDs in the graph are fixture CI IDs, not Core/Twin registry IDs.
    Links store consumer -> dependency (impact walks the reverse direction).
    """
    fixture = load_fixture_bytes(raw)
    report = validate_fixture(fixture)
    digest = hashlib.sha256(raw).hexdigest()
    namespace = fixture["organization"]

    def evidence(pointer: str) -> dict[str, Any]:
        return {
            "source": "LOCAL_SYNTHETIC_FIXTURE",
            "source_ref": SOURCE_PATH + "#" + pointer,
            "namespace": namespace,
            "source_sha": None,
            "source_sha256": digest,
            "observed_at": None,
            "freshness": "UNKNOWN",
            "scope": "STORY_OFFLINE",
        }

    nodes, edges = [], []
    for i, ci in enumerate(fixture["ci"]):
        ident = ci["id"]
        nodes.append({
            "node_id": ident, "kind": ci["kind"], "name": ci["name"],
            "state": "UNKNOWN", "resource_id": None, "service_id": None,
            "provenance": evidence(f"/ci/{i}"),
        })
        for j, dependency in enumerate(ci["depends_on"]):
            edges.append({
                "source_id": ident, "target_id": dependency,
                "relation_type": "DEPENDS_ON",
                "provenance": evidence(f"/ci/{i}/depends_on/{j}"),
            })
    nodes.sort(key=lambda x: x["node_id"])
    edges.sort(key=lambda x: (x["source_id"], x["target_id"]))
    path = report["impact_path"]
    edge_index = {(e["source_id"], e["target_id"]): e for e in edges}
    path_edges = [edge_index[(consumer, dependency)]
                  for dependency, consumer in zip(path, path[1:])]
    affected = report["affected_ci_ids"]
    root = path[0]
    target = path[-1]
    # Preserve alternative direct dependencies of every structurally reachable
    # consumer, without assuming availability or AND/OR failover semantics.
    alternate = sorted({e["target_id"] for e in edges
                        if e["source_id"] in affected
                        and e["target_id"] not in affected})
    return {
        "schema": SCHEMA,
        "scope": "STORY_OFFLINE", "namespace": namespace,
        "tenant_id": None, "incident_id": report["source_incident_id"],
        "impact_incident_id": report["target_incident_id"],
        "run_id": "SIM-ACME-" + digest[:16].upper(),
        "attempt_id": None, "core_run_id": None, "service_id": None,
        "resource_id": None, "binding_status": "UNBOUND",
        "source_sha256": digest, "source_sha": None,
        "observed_at": None, "freshness": "UNKNOWN",
        "nodes": nodes, "edges": edges,
        "impact": {
            "root_node_id": root, "target_node_id": target,
            "impact_path": path, "path_edges": path_edges,
            "affected_ci_ids": affected,
            "reachable_ci_count_including_root": len(affected),
            "downstream_ci_count": len(affected) - 1,
            "alternative_dependency_ids": alternate,
            "alternative_dependency_health": "UNKNOWN",
            "dependency_failure_semantics": "UNKNOWN",
            "status": "STRUCTURAL_HYPOTHESIS_ONLY",
            "operational_impact": "UNKNOWN",
            "causality_confirmed": False,
        },
        "runtime_attested": False, "production_qualified": False,
        "live_remediation_authorized": False,
    }
