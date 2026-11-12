"""Fail-closed, network-free V30 observability read-model contract.

This module validates already-fetched samples; it never executes PromQL or SQL.
"""
from datetime import datetime, timezone
from math import isfinite

ALLOWED_METRICS = {
    "node_cpu_utilization": ("ratio", 300),
    "node_memory_used": ("bytes", 300),
    "node_filesystem_available": ("bytes", 300),
    "http_requests_rate": ("requests/second", 120),
}
ALLOWED_MODES = {"LIVE", "DEMO", "REPLAY"}


def metric_read_model(*, actor, tenant, authorized_tenants, metric, value,
                      observed_at, now, source, mode, window_seconds,
                      generation, expected_generation):
    """Return safe envelope. Authorization is mandatory before sample inspection.

    Caller MUST derive actor/tenant/authorized_tenants from verified server session,
    not from browser parameters. This function is not an authentication adapter.
    """
    if (not isinstance(actor, str) or not actor.strip()
            or not isinstance(tenant, str) or not tenant.strip()):
        return {"http_status": 401, "state": "BLOCKED", "data": None, "reason": "UNAUTHENTICATED"}
    if (not isinstance(authorized_tenants, (set, frozenset, tuple, list))
            or tenant not in authorized_tenants):
        return {"http_status": 403, "state": "BLOCKED", "data": None, "reason": "TENANT_DENIED"}
    if mode not in ALLOWED_MODES or metric not in ALLOWED_METRICS:
        return {"http_status": 400, "state": "BLOCKED", "data": None, "reason": "INVALID_SCOPE"}
    if (type(generation) is not int or type(expected_generation) is not int
            or generation < 0 or generation != expected_generation):
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "STALE_GENERATION"}
    unit, max_age = ALLOWED_METRICS[metric]
    if not isinstance(window_seconds, int) or isinstance(window_seconds, bool) or not 0 < window_seconds <= 3600:
        return {"http_status": 400, "state": "BLOCKED", "data": None, "reason": "INVALID_WINDOW"}
    if not isinstance(source, str) or source not in {"prometheus:v30", "prometheus:replay"}:
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "SOURCE_UNATTESTED"}
    if ((mode == "LIVE" and source != "prometheus:v30")
            or (mode == "REPLAY" and source != "prometheus:replay")
            or mode == "DEMO"):
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "MODE_SOURCE_MISMATCH"}
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "INVALID_SAMPLE"}
    # A syntactically finite sample is not necessarily a meaningful measurement.
    # Never present impossible utilization or negative counts as observed health.
    if ((metric == "node_cpu_utilization" and not 0 <= value <= 1)
            or (metric in {"node_memory_used", "node_filesystem_available", "http_requests_rate"}
                and value < 0)):
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "OUT_OF_RANGE_SAMPLE"}
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if not isinstance(now, datetime) or observed.tzinfo is None or now.tzinfo is None:
            raise ValueError("timezone required")
        age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    except (AttributeError, TypeError, ValueError, OverflowError):
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "INVALID_TIMESTAMP"}
    if age < 0 or age > max_age:
        return {"http_status": 200, "state": "UNKNOWN", "data": None, "reason": "STALE_SAMPLE"}
    return {"http_status": 200, "state": "READY",
            "data": {"metric": metric, "value": value, "unit": unit,
                     "window_seconds": window_seconds, "observed_at": observed_at,
                     "freshness_seconds": age, "source": source, "mode": mode,
                     "generation": generation}, "reason": None}
