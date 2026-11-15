"""Offline, read-only dependency projection; never an authoritative CMDB or LIVE proof."""
from __future__ import annotations

from datetime import datetime, timezone

SCHEMA = "aiops2.twin-dependency-read.v1"
KINDS = frozenset({"SAN", "STORAGE", "SERVICE"})
AUTHORITIES = frozenset({"GLPI_CMDB", "VERIFIED_CMDB_EXPORT"})


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def project_dependencies(nodes, edges, *, tenant_id, as_of, max_age_seconds=900):
    """Project only tenant-scoped, source-backed edges; everything else UNKNOWN.

    A fixture may carry source metadata but is never considered LIVE attestation.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant required")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("nodes and edges must be lists")
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("invalid freshness window")
    now = _utc(as_of)
    index = {}
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"id", "kind", "tenant_id"}:
            raise ValueError("invalid node")
        if not all(isinstance(node[k], str) and node[k].strip() for k in node):
            raise ValueError("invalid node identity")
        if node["kind"] not in KINDS or node["tenant_id"] != tenant_id:
            raise ValueError("cross-tenant or invalid node")
        if node["id"] in index:
            raise ValueError("duplicate node")
        index[node["id"]] = dict(node)
    results = []
    seen = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("invalid edge")
        if set(edge) != {"from", "to", "tenant_id", "authority", "source_ref", "observed_at", "attested"}:
            raise ValueError("invalid edge contract")
        a, b = edge["from"], edge["to"]
        if not isinstance(a, str) or not isinstance(b, str) or a not in index or b not in index:
            raise ValueError("edge endpoint not in tenant graph")
        if edge["tenant_id"] != tenant_id:
            raise ValueError("cross-tenant edge")
        key = (a, b)
        if key in seen:
            raise ValueError("duplicate edge")
        seen.add(key)
        valid_direction = (index[a]["kind"], index[b]["kind"]) in {
            ("SAN", "STORAGE"), ("STORAGE", "SERVICE")
        }
        source = edge["source_ref"]
        source_valid = isinstance(source, str) and bool(source.strip())
        try:
            age = (now - _utc(edge["observed_at"])).total_seconds()
            fresh = 0 <= age <= max_age_seconds
        except ValueError:
            fresh = False
        proved = (valid_direction and edge["authority"] in AUTHORITIES
                  and source_valid and edge["attested"] is True and fresh)
        results.append({"from": a, "to": b, "state": "SOURCED" if proved else "UNKNOWN",
                        "source_ref": source if source_valid else None,
                        "authority": edge["authority"] if edge["authority"] in AUTHORITIES else "UNKNOWN",
                        "freshness": "FRESH" if fresh else "UNKNOWN"})
    return {"schema": SCHEMA, "mode": "DEMO_FIXTURE", "tenant_id": tenant_id,
            "nodes": sorted(index.values(), key=lambda n: n["id"]),
            "edges": sorted(results, key=lambda e: (e["from"], e["to"])),
            "runtime_attested": False, "live_remediation_authorized": False}
