"""Deterministic declared ACME dependency graph; never a discovered/healthy topology.

Targeted adaptation of PR #36 demo/noc_topology.py's read-only graph idea
to the canonical validated ACME fixture. No NOC/GLPI/Core network calls.
"""
from __future__ import annotations

from collections import deque

from portal.acme_fixture_contract import validate_fixture

SOURCE_FABRIC = "SAN-FABRIC-A"
ALTERNATE_FABRIC = "SAN-FABRIC-B"
PAYMENTS = "APP-PAY-01"


def _declared_path(consumers: dict[str, list[str]], source: str, target: str) -> list[str] | None:
    if source not in consumers or target not in consumers:
        return None
    pending = deque([(source, [source])])
    visited = set()
    while pending:
        node, path = pending.popleft()
        if node == target:
            return path
        if node in visited:
            continue
        visited.add(node)
        for child in sorted(consumers[node]):
            if child not in visited:
                pending.append((child, path + [child]))
    return None


def build_declared_topology(fixture: dict) -> dict:
    """Validate before deriving any node/edge; runtime status is always UNKNOWN."""
    report = validate_fixture(fixture)
    cis = {ci["id"]: ci for ci in fixture["ci"]}
    consumers = {ci_id: [] for ci_id in cis}
    edges = []
    for consumer, ci in cis.items():
        for dependency in ci["depends_on"]:
            consumers[dependency].append(consumer)
            edges.append({
                "from": dependency, "to": consumer,
                "relation": "DECLARED_DEPENDENCY_NOT_RUNTIME_DISCOVERY",
            })
    edges.sort(key=lambda edge: (edge["from"], edge["to"]))
    affected = set(report["affected_ci_ids"])
    nodes = [
        {
            "id": ci_id,
            "kind": cis[ci_id]["kind"],
            "name": cis[ci_id]["name"],
            "affected_by_source": ci_id in affected,
            "incident_id": (
                report["source_incident_id"] if ci_id == SOURCE_FABRIC
                else report["target_incident_id"] if ci_id == PAYMENTS
                else None
            ),
            "runtime_health": "UNKNOWN",
        }
        for ci_id in sorted(cis)
    ]
    alternate_path = _declared_path(consumers, ALTERNATE_FABRIC, PAYMENTS)
    return {
        "schema": "aiops.acme.declared-topology.v1",
        "provenance": "LOCAL_SYNTHETIC_FIXTURE_ONLY",
        "nodes": nodes,
        "edges": edges,
        "source_incident_id": report["source_incident_id"],
        "impact_incident_id": report["target_incident_id"],
        "declared_impact_path": report["impact_path"],
        "affected_ci_ids": report["affected_ci_ids"],
        "alternate_fabric_id": ALTERNATE_FABRIC if alternate_path else None,
        "alternate_declared_path": alternate_path,
        "alternate_path_status": "DECLARED_NOT_VERIFIED" if alternate_path else "UNKNOWN",
        "failover_verified": False,
        "runtime_health": "UNKNOWN",
        "cmdb_verified": False,
        "live_discovery": False,
        "canonical_run_id": None,
        "glpi_ticket_id": None,
        "glpi_ticket_url": None,
        "live_remediation_authorized": False,
    }
