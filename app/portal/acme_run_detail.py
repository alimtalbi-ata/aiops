"""Main-based, read-only synthetic Core Run detail; no tenant or approval authority.

Only the already-existing internal-bearer Core NOC Run read is consumed.
Events, Evidence refs, AI Ledger and HITL are deliberately UNKNOWN until
a scoped, authenticated Core read contract is available on main.
"""
from __future__ import annotations

import html
import urllib.error
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from portal.noc_correlation import _read_core_run
from portal.noc_runtime import IDENTIFIER, _require_portal_read_auth
from shared.tenant_scope import reject_unqualified_tenant_scope

router = APIRouter()
SECURITY = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}
JOURNEY = ("Incident", "Run", "Evidence", "AI Ledger", "Policy", "HITL", "Verification")
FORBIDDEN_COLLECTIONS = frozenset(
    {"events", "gates", "stages", "evidence", "evidence_refs",
     "demo_artifacts", "artifacts", "ai_ledger", "analyses", "critiques"}
)


def _valid_run_id(value: object) -> bool:
    return (isinstance(value, str) and value.startswith("RUN-")
            and IDENTIFIER.fullmatch(value) is not None)


def _project(rid: str, raw: object) -> dict:
    """Project only four exact synthetic identity fields from Core, never a ledger."""
    if not isinstance(raw, dict) or FORBIDDEN_COLLECTIONS.intersection(raw):
        raise ValueError("Core identity contains unqualified collections")
    reject_unqualified_tenant_scope(raw)
    if (raw.get("run_id") != rid or not _valid_run_id(raw.get("run_id"))
            or not isinstance(raw.get("incident_id"), str)
            or not raw["incident_id"].startswith("INC-")
            or IDENTIFIER.fullmatch(raw["incident_id"]) is None
            or raw.get("mode") not in ("DEMO", "REPLAY", "STORY")
            or not isinstance(raw.get("status"), str)
            or not 1 <= len(raw["status"]) <= 64):
        raise ValueError("Core Run identity mismatch")
    return {
        "schema": "aiops.portal.synthetic-run-detail.v1",
        "state": "SOURCE_VERIFIED_SYNTHETIC_ONLY",
        "connection_state": "CONNECTED",
        "provenance": "SYNTHETIC",
        "source": "CORE_INTERNAL_BEARER_NOC_RUN_READ",
        "run_id": rid,
        "incident_id": raw["incident_id"],
        "mode": raw["mode"],
        "run_status": raw["status"],
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "live_remediation_authorized": False,
        "journey": {
            "Incident": {"state": "SYNTHETIC_REFERENCE_ONLY"},
            "Run": {"state": "SOURCE_VERIFIED_SYNTHETIC_ONLY"},
            "Evidence": {"state": "UNKNOWN", "reason": "CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING"},
            "AI Ledger": {"state": "UNKNOWN", "reason": "CORE_BEARER_LEDGER_READ_NOT_QUALIFIED"},
            "Policy": {"state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED"},
            "HITL": {"state": "UNKNOWN", "reason": "NO_PORTAL_APPROVAL_AUTHORITY"},
            "Verification": {"state": "UNKNOWN", "reason": "NO_RUNTIME_ATTESTATION"},
        },
    }


def _read(rid: str, authorization: str | None) -> tuple[int, dict]:
    # Authenticate before path validation or Core I/O; no browser token is requested.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return exc.status_code, {"state": "UNAUTHORIZED" if exc.status_code == 401 else "UNKNOWN",
                                 "reason": exc.detail}
    if not _valid_run_id(rid):
        return 422, {"state": "UNKNOWN", "reason": "INVALID_RUN_ID"}
    try:
        return 200, _project(rid, _read_core_run(rid))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return exc.code, {"state": "UNAUTHORIZED", "reason": "CORE_READ_DENIED"}
        return 503, {"state": "UNAVAILABLE", "reason": "CORE_READ_UNAVAILABLE"}
    except (OSError, TimeoutError):
        return 503, {"state": "UNAVAILABLE", "reason": "CORE_READ_UNAVAILABLE"}
    except Exception:
        # Includes malformed collections, foreign IDs, tenant claims and bad Core config.
        return 503, {"state": "UNKNOWN", "reason": "CORE_RUN_UNVERIFIED"}


@router.get("/api/portal/runs/{rid}", name="portal_read_only_run_detail")
def run_detail_api(rid: str, authorization: str | None = Header(default=None)):
    status, data = _read(rid, authorization)
    return JSONResponse(data, status_code=status, headers={
        **SECURITY, **({"WWW-Authenticate": "Bearer"} if status == 401 else {})})


@router.get("/runs/{rid}", response_class=HTMLResponse, name="portal_run_detail_page")
def run_detail_page(rid: str, authorization: str | None = Header(default=None)):
    status, data = _read(rid, authorization)
    safe_rid = html.escape(rid if _valid_run_id(rid) else "UNKNOWN", quote=True)
    safe_state = html.escape(data["state"], quote=True)
    nav = " · ".join(
        f'<a href="#{name.lower().replace(" ", "-")}">{html.escape(name)}</a>'
        for name in JOURNEY
    )
    rows = []
    for name in JOURNEY:
        item = data.get("journey", {}).get(name, {"state": "UNKNOWN", "reason": data.get("reason", "AUTH_REQUIRED")})
        title = html.escape(name)
        item_state = html.escape(item["state"], quote=True)
        reason = html.escape(item.get("reason", "SOURCE_ONLY_NOT_RUNTIME_ATTESTED"), quote=True)
        rows.append(
            f'<section id="{name.lower().replace(" ", "-")}" class="panel">'
            f'<h2>{title}</h2><p>{item_state}</p><p class="muted">{reason}</p></section>'
        )
    source = html.escape(data.get("source", "UNKNOWN"), quote=True)
    provenance = html.escape(data.get("provenance", "UNKNOWN"), quote=True)
    mode = html.escape(data.get("mode", "UNKNOWN"), quote=True)
    # Requested ID is NOT presented as an authenticated Run unless Core matched it.
    heading = "Core-verified Run" if status == 200 else "Requested Run — NOT VERIFIED"
    page = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>ACME — Run detail</title><style>'
        'body{background:#07111d;color:#e9f2f8;font:15px system-ui,sans-serif;margin:0}'
        'main{max-width:1100px;margin:auto;padding:24px}'
        'a{color:#8fd0ff}nav{line-height:2}.panel{background:#0c1d2d;'
        'border:1px solid #23445b;border-radius:14px;padding:18px;margin:14px 0}'
        '.muted{color:#a8c0d0}code{overflow-wrap:anywhere}</style></head><body><main>'
        '<header><a href="/">← Cockpit NOC / portail unique</a></header>'
        f'<h1>{heading}: <code>{safe_rid}</code></h1>'
        f'<p role="status">State: {safe_state} · provenance: {provenance} · '
        f'mode: {mode} · source: {source}</p>'
        '<p class="muted">Tenant ACL: NOT QUALIFIED. No Evidence bytes, AI decision, '
        'HITL approval, Payments impact or verification is attested here.</p>'
        f'<nav aria-label="ACME journey">{nav}</nav>{"".join(rows)}'
        '</main></body></html>'
    )
    return HTMLResponse(page, status_code=status, headers={
        **SECURITY, **({"WWW-Authenticate": "Bearer"} if status == 401 else {})})


@router.get("/assets/portal-run-link.js")
def portal_run_link_script():
    return FileResponse(Path(__file__).with_name("portal_run_link_client.js"),
                        media_type="application/javascript", headers=SECURITY)
