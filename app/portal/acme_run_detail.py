"""Main-based read-only Run journey, with no tenant or approval authority.

The internal-bearer Core NOC read does NOT establish a viewer's tenant ACL.
Never disclose its Run/Incident identity or status through the Portal until
Core supplies a server-authorized, exact-Run, tenant-scoped read contract.
"""
from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from portal.core_acl_consumer import consume_run_acl
from portal.oidc_session import _SESSION_COOKIE, _session_from_cookie
from portal.noc_correlation import _read_core_run
from portal.noc_runtime import IDENTIFIER, _require_portal_read_auth
from shared.domain import STATUSES
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

JOURNEY = ("Incident", "Run", "Evidence", "AI Ledger", "Policy", "HITL", "Verification", "GLPI")
FORBIDDEN_COLLECTIONS = frozenset(
    {"events", "gates", "stages", "evidence", "evidence_refs",
     "demo_artifacts", "artifacts", "ai_ledger", "analyses", "critiques"}
)

# The current Core NOC Run endpoint returns only four identity fields.
# Any extra authority, provenance or impact claim is unqualified by this reader.
UNQUALIFIED_CLAIMS = frozenset({
    "synthetic", "runtime_authenticated", "runtime_attested",
    "tenant_acl_qualified", "live_remediation_authorized",
    "evidence_runtime_attested", "source_observed_at", "source_freshness",
    "connection_state", "provenance", "ticket_id", "evidence_id",
    "payments_impact", "impact",
})


def _valid_run_id(value: object) -> bool:
    return (isinstance(value, str) and value.startswith("RUN-")
            and IDENTIFIER.fullmatch(value) is not None)


def _project(rid: str, raw: object) -> dict:
    """Validate Core's four-field envelope; expose no tenant data to viewers."""
    if (not isinstance(raw, dict) or FORBIDDEN_COLLECTIONS.intersection(raw)
            or UNQUALIFIED_CLAIMS.intersection(raw)):
        raise ValueError("Core identity contains unqualified claims")
    reject_unqualified_tenant_scope(raw)
    # Core /api/noc/runs/{rid} has exactly four qualified identity fields.
    # Fail closed on any new field, even if its name is not yet denylisted.
    if set(raw) != {"run_id", "incident_id", "mode", "status"}:
        raise ValueError("Core Run identity has unqualified fields")
    if (raw.get("run_id") != rid or not _valid_run_id(raw.get("run_id"))
            or not isinstance(raw.get("incident_id"), str)
            or not raw["incident_id"].startswith("INC-")
            or IDENTIFIER.fullmatch(raw["incident_id"]) is None
            or raw.get("mode") not in ("DEMO", "REPLAY", "STORY")
            or not isinstance(raw.get("status"), str)
            or raw["status"] not in STATUSES):
        raise ValueError("Core Run identity mismatch")
    # CONNECTED describes only the internal Core transport, NOT tenant access.
    # Do not include even a synthetic Run ID, incident ID, mode or status:
    # they are tenant data until an independent server-side ACL is enforced.
    return _unqualified_run()


def _unqualified_run() -> dict:
    """Constant fail-closed projection, independent of Core Run existence."""
    return {
        "schema": "aiops.portal.run-detail.v1",
        "state": "UNKNOWN",
        "reason": "TENANT_ACL_NOT_QUALIFIED",
        "connection_state": "UNKNOWN",
        "provenance": "UNKNOWN",
        "source": "UNKNOWN",
        "source_observed_at": None,
        "source_freshness": "UNKNOWN",
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "live_remediation_authorized": False,
        "journey": {
            "Incident": {"state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED"},
            "Run": {"state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED"},
            "Evidence": {"state": "UNKNOWN", "reason": "CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING"},
            "AI Ledger": {"state": "UNKNOWN", "reason": "CORE_BEARER_LEDGER_READ_NOT_QUALIFIED"},
            "Policy": {"state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED"},
            "HITL": {"state": "UNKNOWN", "reason": "NO_PORTAL_APPROVAL_AUTHORITY"},
            "Verification": {"state": "UNKNOWN", "reason": "NO_RUNTIME_ATTESTATION"},
            "GLPI": {"state": "UNKNOWN", "reason": "NO_TENANT_SCOPED_TICKET_RUN_LINK"},
        },
    }


def _oidc_cookie_supplied(request: Request) -> bool:
    """A supplied OIDC cookie must never downgrade to shared viewer auth.

    Invalid, expired and revoked handles are still an explicit attempt to use
    the server-side identity channel. consume_run_acl returns 401 for them.
    The viewer bearer remains identity-only and cannot rescue this attempt.
    """
    return _SESSION_COOKIE in request.cookies


def _session_failure(status: int, detail: str, headers: dict | None = None) -> JSONResponse:
    # Preserve HTTP auth status while applying the same response protections as
    # the read-only Run page and JSON projection, including rejected exchanges.
    return JSONResponse({"detail": detail}, status_code=status, headers={
        **(headers or {}), **SECURITY,
        **({"WWW-Authenticate": "Bearer"} if status == 401 else {}),
    })


@router.post("/api/portal/run-session", name="portal_create_short_lived_run_session")
def create_run_session(request: Request, authorization: str | None = Header(default=None),
                       x_portal_run_id: str | None = Header(default=None)):
    # A shared viewer bearer proves authentication, not exact-Run authorization.
    # Refuse session issuance until a server-derived actor+tenant ACL exists.
    # Even a valid/forged Run ID must not produce a browser capability.
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urllib.parse.urlsplit(origin)
            host = request.headers.get("host", "")
            if (parsed.scheme != "https" or not parsed.netloc
                    or parsed.netloc.lower() != host.lower()
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
                return _session_failure(403, "same_origin_required")
        except ValueError:
            return _session_failure(403, "same_origin_required")
    try:
        _require_portal_read_auth(authorization)
        if not _valid_run_id(x_portal_run_id):
            return JSONResponse({"state": "UNKNOWN", "reason": "INVALID_RUN_ID"},
                                status_code=422, headers=SECURITY)
    except HTTPException as exc:
        return _session_failure(exc.status_code, str(exc.detail), exc.headers)
    # No Core/GLPI request and no Set-Cookie: a shared bearer cannot issue
    # a capability for an unverified or foreign Run.
    return JSONResponse(_unqualified_run(), status_code=503, headers=SECURITY)


def _read(rid: str, authorization: str | None) -> tuple[int, dict]:
    # Authenticate before path validation or Core I/O; no browser token is requested.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return exc.status_code, {"state": "UNAUTHORIZED" if exc.status_code == 401 else "UNKNOWN",
                                 "reason": exc.detail}
    if not _valid_run_id(rid):
        return 422, {"state": "UNKNOWN", "reason": "INVALID_RUN_ID"}
    # The shared viewer bearer is authentication, never actor/tenant authority.
    # No server-derived exact-Run ACL exists: do not fetch Core even to check
    # whether this Run exists. A constant response avoids presence/timing oracles.
    return 503, _unqualified_run()


@router.get("/api/portal/runs/{rid}", name="portal_read_only_run_detail")
def run_detail_api(rid: str, request: Request,
                   authorization: str | None = Header(default=None)):
    # A server-stored OIDC session is identity, never an exact-Run grant.
    # Retain the legacy bearer refusal for clients without such a session.
    if _oidc_cookie_supplied(request):
        status, reason = consume_run_acl(request, rid)
        data = _unqualified_run() if status == 503 else {"state": "UNAUTHORIZED", "reason": reason}
    else:
        status, data = _read(rid, authorization)
    return JSONResponse(data, status_code=status, headers={
        **SECURITY, **({"WWW-Authenticate": "Bearer"} if status == 401 else {})})


@router.get("/runs/{rid}", response_class=HTMLResponse, name="portal_run_detail_page")
def run_detail_page(rid: str, request: Request,
                     authorization: str | None = Header(default=None)):
    # Previously minted viewer cookies are not actor+tenant authority.
    # Do not upgrade them into a bearer identity, even during their TTL.
    if _oidc_cookie_supplied(request):
        status, reason = consume_run_acl(request, rid)
        data = _unqualified_run() if status == 503 else {"state": "UNAUTHORIZED", "reason": reason}
    else:
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
    freshness = html.escape(data.get("source_freshness", "UNKNOWN"), quote=True)
    connection = html.escape(
        data.get("connection_state", data["state"] if data["state"] in
                 ("UNAUTHORIZED", "UNAVAILABLE", "NOT_INSTALLED") else "UNKNOWN"),
        quote=True,
    )
    # Requested ID is NOT presented as an authenticated Run unless Core matched it.
    heading = "Tenant-authorized Run" if status == 200 and data.get("tenant_acl_qualified") is True else "Requested Run — NOT VERIFIED"
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
        '<p role="note" data-story-provenance="SYNTHETIC">'
        'ACME P1 SAN→Payments — SYNTHETIC story context only; '
        'not linked to this Run or runtime-attested.</p>'
        f'<h1>{heading}: <code>{safe_rid}</code></h1>'
        f'<p role="status">State: {safe_state} · provenance: {provenance} · '
        f'mode: {mode} · connection: {connection} · source: {source} · source freshness: {freshness}</p>'
        '<p class="muted">Tenant ACL: NOT QUALIFIED. No Evidence bytes, AI decision, '
        'HITL approval, Payments impact or verification is attested here.</p>'
        '<p><a href="/itsm">GLPI / ITSM native handoff — read-only, UNKNOWN</a></p>'
        f'<nav aria-label="ACME journey">{nav}</nav>{"".join(rows)}'
        '</main></body></html>'
    )
    return HTMLResponse(page, status_code=status, headers={
        **SECURITY, **({"WWW-Authenticate": "Bearer"} if status == 401 else {})})


@router.get("/assets/portal-run-link.js")
def portal_run_link_script():
    return FileResponse(Path(__file__).with_name("portal_run_link_client.js"),
                        media_type="application/javascript", headers=SECURITY)
