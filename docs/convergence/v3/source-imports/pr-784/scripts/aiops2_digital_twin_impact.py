"""Sourced, tenant-scoped synthetic Digital Twin impact resolution.

No network access, inferred CMDB links or live effects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections import deque

from aiops2_event_correlation import InvalidEvent, _timestamp


def resolve_impact(incident: object, edges: object, *, as_of: str, max_age_seconds: int = 86400, max_path_expansions: int = 10000) -> dict:
    """Find explicitly sourced paths from incident CIs to its service.

    Unknown or invalid links are rejected; a path is not a runtime attestation.
    """
    if not isinstance(incident, dict) or not isinstance(edges, list):
        raise InvalidEvent("invalid incident or edges")
    tenant = incident.get("tenant_id")
    service = incident.get("service_id")
    incident_id = incident.get("incident_id")
    events = incident.get("events")
    if (not isinstance(tenant, str) or not 1 <= len(tenant) <= 256
            or not isinstance(service, str) or not 1 <= len(service) <= 256):
        raise InvalidEvent("invalid incident identity")
    if not isinstance(incident_id, str) or not 1 <= len(incident_id) <= 256:
        raise InvalidEvent("invalid incident id")
    if not isinstance(events, list) or not events:
        raise InvalidEvent("incident has no events")
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise InvalidEvent("invalid max age")
    if type(max_path_expansions) is not int or max_path_expansions < 1:
        raise InvalidEvent("invalid path expansion budget")
    now = _timestamp(as_of)
    sources = set()
    for event in events:
        if (not isinstance(event, dict) or event.get("tenant_id") != tenant
                or event.get("service_id") != service):
            raise InvalidEvent("cross-tenant or invalid incident event")
        ci = event.get("ci_id")
        if not isinstance(ci, str) or not 1 <= len(ci) <= 256:
            raise InvalidEvent("invalid incident CI")
        sources.add(ci)
        if len(sources) > 100:
            raise InvalidEvent("incident CI origin budget exceeded")
    graph = {}
    rejected = []
    seen_edges = set()
    edge_claims = {}
    relation_digests = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            rejected.append({"index": index, "reason": "invalid edge"})
            continue
        if edge.get("tenant_id") != tenant:
            rejected.append({"index": index, "reason": "tenant mismatch"})
            continue
        if any(not isinstance(edge.get(k), str) or not edge[k].strip()
               for k in ("from_id", "to_id", "source_id", "evidence_sha256", "observed_at")):
            rejected.append({"index": index, "reason": "missing edge provenance"})
            continue
        if any(len(edge[field]) > 256 for field in ("from_id", "to_id", "source_id")):
            rejected.append({"index": index, "reason": "oversized edge identity"})
            continue
        if len(edge["evidence_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in edge["evidence_sha256"]):
            rejected.append({"index": index, "reason": "invalid edge digest"})
            continue
        try:
            age = (now - _timestamp(edge["observed_at"])).total_seconds()
        except InvalidEvent:
            rejected.append({"index": index, "reason": "invalid edge timestamp"})
            continue
        if age < 0 or age > max_age_seconds:
            rejected.append({"index": index, "reason": "stale or future edge"})
            continue
        edge_key = (edge["tenant_id"], edge["from_id"], edge["to_id"],
                    edge["source_id"], edge["evidence_sha256"],
                    _timestamp(edge["observed_at"]).isoformat())
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        relation_key = (edge["from_id"], edge["to_id"])
        relation_digests.setdefault(relation_key, set()).add(edge["evidence_sha256"])
        claim_key = (edge["from_id"], edge["to_id"], edge["source_id"])
        edge_claims.setdefault(claim_key, []).append((index, edge))
    # Preserve every distinct receipt index for audit, even when repeated
    # observations of a source claim collapse to one graph relation.
    relation_claims = {}
    for claims in edge_claims.values():
        if len({e["evidence_sha256"] for _, e in claims}) > 1:
            rejected.extend({"index": i, "reason": "conflicting edge evidence"}
                            for i, _ in claims)
        else:
            e = claims[0][1]
            relation_claims.setdefault((e["from_id"], e["to_id"]), []).extend(claims)
    # A relation tainted by any conflicting digest cannot be proven by
    # another source. Quarantine all remaining receipts of that relation.
    for (origin, destination), claims in relation_claims.items():
        if len(relation_digests[(origin, destination)]) > 1:
            rejected.extend({"index": i, "reason": "conflicting relation evidence"}
                            for i, _ in claims)
        else:
            representative = min(
                (e for _, e in claims),
                key=lambda e: (e["source_id"], _timestamp(e["observed_at"])))
            graph.setdefault(origin, []).append(representative)
    rejected.sort(key=lambda entry: entry["index"])
    for neighbors in graph.values():
        neighbors.sort(key=lambda e: (e["to_id"], e["source_id"], e["evidence_sha256"]))
    paths = []
    expansions = 0
    queued = 0
    exhausted = False
    for start in sorted(sources):
        queued += 1
        if queued > max_path_expansions:
            exhausted = True
            break
        queue = deque([(start, [start], [])])
        while queue:
            expansions += 1
            if expansions > max_path_expansions:
                exhausted = True
                break
            node, nodes, proof = queue.popleft()
            if node == service and proof:
                paths.append({"nodes": nodes, "evidence_sha256": proof})
                if len(paths) > 100:
                    exhausted = True
                    break
                continue
            # The downstream Analyst/Critic and HTML contracts cap path depth at 100.
            if len(nodes) >= 100 and any(
                    edge["to_id"] not in nodes for edge in graph.get(node, [])):
                exhausted = True
                break
            for edge in graph.get(node, []):
                nxt = edge["to_id"]
                if nxt not in nodes:
                    queued += 1
                    if queued > max_path_expansions:
                        exhausted = True
                        break
                    queue.append((nxt, nodes + [nxt], proof + [edge["evidence_sha256"]]))
            if exhausted:
                break
        if exhausted:
            break
    # Never return a partially enumerated proof set after resource exhaustion.
    if exhausted:
        paths = []
    paths.sort(key=lambda p: (len(p["nodes"]), p["nodes"], p["evidence_sha256"]))
    return {
        "schema": "aiops2.synthetic-impact-resolution.v1",
        "incident_id": incident_id,
        "tenant_id": tenant,
        "service_id": service,
        "impact_state": "SOURCED_SYNTHETIC_PATH" if paths else "UNKNOWN",
        "paths": paths,
        "resource_budget_exhausted": exhausted,
        "rejected_edges": rejected,
        "runtime_attested": False,
        "live_remediation_authorized": False,
    }
