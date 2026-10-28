"""Read-only Core/Twin aggregation; failed or malformed upstreams are UNKNOWN.

Project only the fields required by the portal. The Core/Twin responses are
untrusted data, not permission to forward extra fields (tokens, evidence, or
unverified attestation claims) to the browser.
"""
from __future__ import annotations

import math

DASHBOARD_KEYS = ("open_p1", "open_incidents", "running", "blocked",
                  "twin_nodes", "degraded_nodes")
RUN_DISPLAY_KEYS = ("run_id", "mode", "status", "overall_confidence", "scenario_id")
TWIN_MAP_KEYS = ("nodes_by_type", "states")


def _bounded_text(value: object, *, required: bool = False) -> bool:
    if value is None:
        return not required
    return (isinstance(value, str) and 0 < len(value) <= 256
            and all(32 <= ord(ch) != 127 for ch in value))


def _project(name: str, data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("upstream schema mismatch")
    if name == "dashboard":
        if not all(type(data.get(key)) is int and data[key] >= 0
                   for key in DASHBOARD_KEYS):
            raise ValueError("invalid dashboard counters")
        return {key: data[key] for key in DASHBOARD_KEYS}
    if name == "runs":
        items = data.get("items")
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("invalid run inventory")
        projected = []
        seen = set()
        for item in items:
            if not isinstance(item, dict) or not _bounded_text(item.get("run_id"), required=True):
                raise ValueError("invalid run identity")
            if item["run_id"] in seen:
                raise ValueError("duplicate run identity")
            seen.add(item["run_id"])
            row = {}
            for key in RUN_DISPLAY_KEYS:
                if key not in item:
                    continue
                value = item[key]
                if key == "overall_confidence":
                    if value is not None and (type(value) not in (int, float)
                                              or not math.isfinite(value)
                                              or not 0 <= value <= 1):
                        raise ValueError("invalid confidence")
                elif not _bounded_text(value, required=(key == "run_id")):
                    raise ValueError("invalid run field")
                row[key] = value
            projected.append(row)
        return {"items": projected}
    if name == "twin":
        if (type(data.get("nodes")) is not int or data["nodes"] < 0
                or type(data.get("edges")) is not int or data["edges"] < 0):
            raise ValueError("invalid twin counters")
        result = {"nodes": data["nodes"], "edges": data["edges"]}
        for key in TWIN_MAP_KEYS:
            if key not in data:
                continue
            value = data[key]
            if (not isinstance(value, dict) or len(value) > 100
                    or not all(_bounded_text(k, required=True)
                               and type(v) is int and v >= 0
                               for k, v in value.items())):
                raise ValueError("invalid twin breakdown")
            result[key] = dict(value)
        return result
    raise ValueError("unknown read model")


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
            result = _project(name, fetch_json(base, path))
        except Exception:
            snapshot[name] = None
            snapshot["states"][name] = "UNKNOWN"
        else:
            snapshot[name] = result
            snapshot["states"][name] = "READABLE_UNVERIFIED"
    return snapshot
