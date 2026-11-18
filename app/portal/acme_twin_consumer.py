"""Consumer projection of the local Twin; never an authenticated binding."""
from collections import deque
from copy import deepcopy
import re


def project_twin_consumer(impact: dict) -> dict:
    """Require consistent story identities; no promotion to runtime authority."""
    twin = impact.get("twin_evidence")
    if not isinstance(twin, dict):
        raise ValueError("missing_twin_evidence")
    digest = impact.get("source_sha256")
    if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or twin.get("schema") != "aiops.acme.twin-provenance.v1"
            or twin.get("namespace") != "ACME-DEMO"
            or twin.get("scope") != "STORY_OFFLINE"
            or twin.get("binding_status") != "UNBOUND"
            or any(k not in twin or twin[k] is not None for k in (
                "tenant_id", "attempt_id", "core_run_id", "resource_id", "service_id",
                "observed_at", "source_sha"))
            or twin.get("freshness") != "UNKNOWN"
            or any(twin.get(k) is not False for k in (
                "runtime_attested", "production_qualified", "live_remediation_authorized"))
            or any(twin.get(k) != impact.get(k) for k in (
                "source_sha256", "incident_id", "impact_incident_id", "run_id"))
            or twin.get("run_id") != "SIM-ACME-" + digest[:16].upper()):
        raise ValueError("twin_story_identity_mismatch")
    graph = twin["impact"]
    if (graph.get("impact_path") != impact.get("impact_path")
            or graph.get("affected_ci_ids") != impact.get("affected_ci_ids")
            or graph.get("operational_impact") != "UNKNOWN"
            or graph.get("causality_confirmed") is not False
            or graph.get("dependency_failure_semantics") != "UNKNOWN"
            or graph.get("alternative_dependency_health") != "UNKNOWN"
            or graph.get("status") != "STRUCTURAL_HYPOTHESIS_ONLY"):
        raise ValueError("twin_impact_mismatch")
    nodes = twin["nodes"]
    edges = twin["edges"]
    ids = {n["node_id"] for n in nodes}
    if len(ids) != len(nodes) or len(ids) != impact.get("ci_count"):
        raise ValueError("twin_node_mismatch")
    for item in nodes + edges:
        p = item["provenance"]
        if (p.get("source") != "LOCAL_SYNTHETIC_FIXTURE"
                or p.get("namespace") != "ACME-DEMO"
                or p.get("source_sha256") != digest
                or p.get("scope") != "STORY_OFFLINE"
                or p.get("freshness") != "UNKNOWN"
                or any(k not in p or p[k] is not None for k in ("observed_at", "source_sha"))
                or not re.fullmatch(r"app/portal/acme-fixtures\.json#/ci/[0-9]+(?:/depends_on/[0-9]+)?", p.get("source_ref", ""))):
            raise ValueError("twin_provenance_mismatch")
    if any(n.get("state") != "UNKNOWN" or any(k not in n or n[k] is not None
           for k in ("resource_id", "service_id")) for n in nodes):
        raise ValueError("twin_node_authority_mismatch")
    reverse = {n: [] for n in ids}
    degree = dict.fromkeys(ids, 0)
    pairs = set()
    for e in edges:
        a, b = e["source_id"], e["target_id"]
        if a not in ids or b not in ids or (a, b) in pairs or e.get("relation_type") != "DEPENDS_ON":
            raise ValueError("twin_edge_mismatch")
        pairs.add((a, b))
        reverse[b].append(a)
        degree[a] += 1
    path = graph["impact_path"]
    root, target = path[0], path[-1]
    if root not in ids or target not in ids or any((b, a) not in pairs for a, b in zip(path, path[1:])):
        raise ValueError("twin_path_mismatch")
    # Count paths in a DAG without materializing exponentially many paths.
    counts = dict.fromkeys(ids, 0)
    counts[root] = 1
    queue = deque(sorted(n for n in ids if degree[n] == 0))
    visited = 0
    while queue:
        n = queue.popleft()
        visited += 1
        for child in sorted(reverse[n]):
            counts[child] += counts[n]
            degree[child] -= 1
            if degree[child] == 0:
                queue.append(child)
    reached = sorted(n for n in ids if counts[n])
    if visited != len(ids) or reached != graph["affected_ci_ids"] or not counts[target]:
        raise ValueError("twin_reachability_mismatch")
    alternate = sorted({b for a, b in pairs if a in reached and b not in reached})
    if alternate != graph["alternative_dependency_ids"]:
        raise ValueError("twin_alternative_mismatch")
    return {
        "schema": "aiops.acme.twin-consumer.v1",
        "story_identity": {k: twin[k] for k in ("namespace", "incident_id", "impact_incident_id", "run_id", "source_sha256")},
        "binding": {k: twin[k] for k in ("scope", "binding_status", "tenant_id", "attempt_id", "core_run_id", "resource_id", "service_id")},
        "freshness": {"status": "UNKNOWN", "observed_at": None, "age_seconds": None, "reason": "NO_RUNTIME_OBSERVATION"},
        "structural_impact": {"root_node_id": root, "target_node_id": target,
                              "path_count_by_ci": {n: counts[n] for n in reached},
                              "target_path_count": counts[target], "affected_ci_ids": reached,
                              "alternative_dependency_ids": alternate, "operational_impact": "UNKNOWN"},
        "hypothesis_citations": [deepcopy(e["provenance"]) for e in edges if e["source_id"] in reached and e["target_id"] in reached],
        "missing_evidence": ["AUTHENTICATED_TENANT_BINDING", "CORE_RUN_ATTEMPT_BINDING", "RUNTIME_OBSERVATION", "REDUNDANCY_HEALTH", "INDEPENDENT_CAUSAL_PROOF"],
        "runtime_attested": False, "live_remediation_authorized": False,
    }
