"""Scoped operator read models. API access is not proof of runtime authenticity.

Viewer: incidents/runs. Operator: incidents/runs + redacted evidence metadata.
No write route, no fallback data, no external redirects or browser credentials.
"""
from __future__ import annotations

import hmac
import math
import os
import re

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
RESOURCE_FIELDS = {
    "incidents": ("incident_id", "external_id", "title", "severity", "state",
                  "service_id", "opened_at", "source", "synthetic"),
    "runs": ("run_id", "incident_id", "mode", "scenario_id", "status",
             "version", "overall_confidence", "created_at", "started_at", "completed_at"),
    "evidence": ("evidence_id", "source", "external_id", "observed_at",
                 "known_at", "claim", "confidence", "payload_hash"),
}
ID_FIELDS = {"incidents": "incident_id", "runs": "run_id", "evidence": "evidence_id"}
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def _token(value: str) -> bool:
    return (isinstance(value, str) and len(value) >= 32 and len(value) <= 256
            and value.isascii() and value.isprintable()
            and not any(ch.isspace() for ch in value))


def require_role(authorization: str | None, env=None) -> str:
    env = os.environ if env is None else env
    viewer = env.get("AIOPS_PORTAL_READ_TOKEN", "")
    operator = env.get("AIOPS_PORTAL_OPERATOR_TOKEN", "")
    if not _token(viewer) or (operator and (not _token(operator) or operator == viewer)):
        raise HTTPException(503, "portal_rbac_not_configured")
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator or not _token(supplied)):
        raise HTTPException(401, "invalid_portal_token")
    if operator and hmac.compare_digest(supplied, operator):
        return "operator"
    if hmac.compare_digest(supplied, viewer):
        return "viewer"
    raise HTTPException(401, "invalid_portal_token")


def _project(name: str, payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("invalid read model envelope")
    items = payload["items"]
    if len(items) > 100:
        raise ValueError("oversized read model")
    projected = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("invalid item")
        ident = item.get(ID_FIELDS[name])
        if not isinstance(ident, str) or IDENTIFIER.fullmatch(ident) is None:
            raise ValueError("invalid canonical identifier")
        # Do not forward arbitrary upstream payloads, secrets or embedded HTML.
        row = {}
        for field in RESOURCE_FIELDS[name]:
            value = item.get(field)
            if value is not None and type(value) not in (str, int, float, bool):
                raise ValueError("unexpected read model field type")
            if isinstance(value, str) and len(value) > 512:
                raise ValueError("oversized read model field")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("invalid numeric read model")
            row[field] = value
        if name == "incidents" and type(row["synthetic"]) is not bool:
            raise ValueError("incident provenance missing")
        projected.append(row)
    return {"items": projected}


def build_operator_snapshot(fetch_json, core_url: str, evidence_url: str, role: str) -> dict:
    if role not in ("viewer", "operator"):
        raise ValueError("invalid portal role")
    result = {"schema": "aiops.portal.operator-read.v1",
              "provenance": "UNATTESTED_UPSTREAM_API_READ",
              "runtime_authenticated": False,
              "live_remediation_authorized": False,
              "role": role, "states": {}, "resources": {}}
    targets = {
        "incidents": (core_url, "/api/incidents"),
        "runs": (core_url, "/api/runs"),
        "evidence": (evidence_url, "/api/evidence?limit=50"),
    }
    for name, (base, path) in targets.items():
        if name == "evidence" and role != "operator":
            result["states"][name] = "FORBIDDEN_BY_ROLE"
            result["resources"][name] = None
            continue
        try:
            result["resources"][name] = _project(name, fetch_json(base, path))
            result["states"][name] = "READABLE_UNVERIFIED"
        except Exception:
            result["resources"][name] = None
            result["states"][name] = "UNKNOWN"
    return result


@router.get("/api/portal/operator/snapshot")
def operator_snapshot(authorization: str | None = Header(default=None)):
    try:
        role = require_role(authorization)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                            headers=HEADERS)
    from shared.http import get_json
    core = os.getenv("CORE_URL", "http://aiops2-core:810")
    evidence = os.getenv("EVIDENCE_URL", "http://aiops2-evidence:812")
    return JSONResponse(build_operator_snapshot(get_json, core, evidence, role),
                        headers=HEADERS)
