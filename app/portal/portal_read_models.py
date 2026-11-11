"""Read-only Core/Twin aggregation; failed or malformed upstreams are UNKNOWN.

No synthetic fallback is produced. This is a UI read model, not runtime
attestation or an authorization decision.
"""
from __future__ import annotations

DASHBOARD_KEYS = ("open_p1", "open_incidents", "running", "blocked",
                  "twin_nodes", "degraded_nodes")

# No authenticated tenant/actor ACL is available at this read boundary.
# Reject tenant-scoped Run inventories rather than displaying cross-tenant data.
# Normalize camelCase, snake_case and kebab-case to avoid spelling bypasses.
TENANT_SCOPE_KEYS = frozenset({
    "tenant", "tenantid", "tenantids", "tenantscope", "tenantaclqualified",
    "organization", "organizationid", "orgid", "workspace", "workspaceid",
    "accountid", "customerid",
})


def _contains_unqualified_tenant_scope(value: object) -> bool:
    """Conservative bounded inspection of JSON-shaped Run inventory fields."""
    pending = [(value, 0)]
    inspected = 0
    while pending:
        node, depth = pending.pop()
        inspected += 1
        if inspected > 2000 or depth > 8:
            return True  # Uninspectable data must not be rendered.
        if isinstance(node, dict):
            if any(isinstance(key, str) and
                   key.replace("_", "").replace("-", "").lower() in TENANT_SCOPE_KEYS
                   for key in node):
                return True
            pending.extend((child, depth + 1) for child in node.values()
                           if isinstance(child, (dict, list)))
        elif isinstance(node, list):
            pending.extend((child, depth + 1) for child in node
                           if isinstance(child, (dict, list)))
    return False


def _valid(name: str, data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if name == "dashboard":
        return all(type(data.get(key)) is int and data[key] >= 0
                   for key in DASHBOARD_KEYS)
    if name == "runs":
        items = data.get("items")
        return (isinstance(items, list) and len(items) <= 100
                and not _contains_unqualified_tenant_scope(data)
                and all(isinstance(item, dict)
                        and isinstance(item.get("run_id"), str)
                        and item["run_id"] for item in items))
    if name == "twin":
        return (type(data.get("nodes")) is int and data["nodes"] >= 0
                and type(data.get("edges")) is int and data["edges"] >= 0)
    return False


def read_portal_snapshot(fetch_json, core_url: str, twin_url: str) -> dict:
    targets = {
        "dashboard": (core_url, "/api/dashboard"),
        "runs": (core_url, "/api/runs"),
        "twin": (twin_url, "/api/twin/summary"),
    }
    snapshot = {"schema": "aiops.portal.readmodels.v1",
                "states": {}, "provenance": "UNATTESTED_UPSTREAM_API_READ",
                "runtime_authenticated": False,
                "tenant_acl_qualified": False,
                "live_remediation_authorized": False}
    for name, (base, path) in targets.items():
        try:
            result = fetch_json(base, path)
            if not _valid(name, result):
                raise ValueError("upstream schema mismatch")
        except Exception:
            snapshot[name] = None
            snapshot["states"][name] = "UNKNOWN"
        else:
            snapshot[name] = result
            snapshot["states"][name] = "READABLE_UNVERIFIED"
    return snapshot
