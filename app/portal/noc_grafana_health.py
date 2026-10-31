"""Grafana HTTP readiness probe; not monitoring evidence or a dashboard attestation.

Uses a fixed internal service origin and a GET-only, bounded, no-redirect request.
No synthetic Grafana response or fallback is ever returned as runtime observation.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from fastapi import APIRouter, Header, HTTPException
from portal import noc_runtime

router = APIRouter()
SCHEMA = "aiops.noc-grafana-connectivity.v1"
MAX_BYTES = 4096
APPROVED_ENDPOINTS = {
    "http://aiops2-grafana:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
}


def _configured_base() -> str:
    base = os.getenv("AIOPS_GRAFANA_READ_URL", "")
    if not base:
        raise ValueError("Grafana not configured")
    if base not in APPROVED_ENDPOINTS:
        raise ValueError("unapproved Grafana endpoint")
    parsed = urllib.parse.urlsplit(base)
    if (parsed.path or parsed.query or parsed.fragment or parsed.username is not None
            or parsed.password is not None):
        raise ValueError("unapproved Grafana endpoint")
    return base


def read_grafana_health() -> dict:
    """Check the real Grafana /api/health; do not infer metrics or tenant access."""
    base = _configured_base()
    url = base + "/api/health"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), noc_runtime._NoRedirect())
    with opener.open(request, timeout=3) as response:
        if response.geturl() != url or response.getcode() != 200:
            raise ValueError("unexpected Grafana response")
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Grafana health not JSON")
        raw = response.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Grafana health response size invalid")
    data = json.loads(raw.decode("utf-8"),
                      object_pairs_hook=noc_runtime._reject_duplicate_keys,
                      parse_constant=noc_runtime._reject_json_constant)
    if (not isinstance(data, dict) or data.get("database") != "ok"
            or not isinstance(data.get("version"), str) or not data["version"]):
        raise ValueError("Grafana health not ready")
    return {
        "schema": SCHEMA,
        "state": "GRAFANA_HTTP_READY_UNATTESTED",
        "source": "REAL_GRAFANA_HTTP_HEALTH",
        "grafana_http_checked": True,
        "grafana_observation": "NOT_TESTED",
        "checkmk_thruk_observation": "NOT_TESTED",
        "tenant_acl_qualified": False,
        "source_runtime_observed": False,
        "runtime_authenticated": False,
        "production_qualified": False,
        "live_remediation_authorized": False,
    }


@router.get("/api/noc/grafana-health", name="noc_grafana_health_readonly")
def grafana_health(authorization: str | None = Header(default=None)):
    try:
        noc_runtime._require_portal_read_auth(authorization)
    except HTTPException as exc:
        return noc_runtime._noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    # HTTP readiness is global, not an actor/tenant-scoped read grant.
    # Do not probe Grafana from the browser route until server-derived ACL exists.
    return noc_runtime._noc_json_response({
        "state": "UNKNOWN",
        "reason": "TENANT_ACL_NOT_QUALIFIED",
        "connection_state": "UNKNOWN",
        "source": "GRAFANA_READINESS_NOT_TENANT_AUTHORIZED",
        "source_freshness": "UNKNOWN",
    }, status_code=503)
