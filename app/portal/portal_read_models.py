"""Read-only Core/Twin aggregation; failed or malformed upstreams are UNKNOWN.

No synthetic fallback is produced. This is a UI read model, not runtime
attestation or an authorization decision.
"""
from __future__ import annotations

DASHBOARD_KEYS = ("open_p1", "open_incidents", "running", "blocked",
                  "twin_nodes", "degraded_nodes")


def _valid(name: str, data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if name == "dashboard":
        return all(type(data.get(key)) is int and data[key] >= 0
                   for key in DASHBOARD_KEYS)
    if name == "runs":
        items = data.get("items")
        return (isinstance(items, list) and len(items) <= 100
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
