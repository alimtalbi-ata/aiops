"""ACME-TEST simulated GLPI ticket readback. Not native GLPI human authority.

This projection is isolated from /api/portal/itsm and never grants READ/READMY.
A successful response requires an authenticated, fixed-path Core sandbox GET;
no browser-provided ticket/tenant/URL is used as authority.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from portal.noc_runtime import _require_portal_read_auth

router = APIRouter()
SCHEMA = "aiops.portal.sim-glpi-readback.v1"
TENANT = "ACME-TEST"
SCENARIO = "ACME-SAN-PAYMENTS"
ATTEMPT = re.compile(r"ACME-SIM-[A-Z0-9_-]{8,80}\Z", re.ASCII)
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z", re.ASCII)
HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; connect-src 'self'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
}
PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACME · Ticket GLPI simulé</title>
<style>
body{margin:0;background:#07111d;color:#e9f2f8;font:15px/1.55 system-ui,sans-serif}
main{max-width:900px;margin:auto;padding:24px}a{color:#91d6ff}
.panel{background:#0c1d2d;border:1px solid #31506a;border-radius:12px;padding:18px;margin:16px 0}
label{display:block;margin:12px 0 4px}input{background:#06111e;color:white;border:1px solid #63839a;border-radius:7px;padding:10px;max-width:100%;width:32em;box-sizing:border-box}
button{background:#204b69;color:white;border:1px solid #8eb9d4;border-radius:8px;padding:9px 12px;margin:8px 8px 8px 0}
button:disabled{opacity:.65}button:focus-visible,input:focus-visible{outline:3px solid #ffda7a}
.badge{display:inline-block;border:1px solid #ffda7a;border-radius:20px;padding:3px 12px;color:#ffda7a;font-weight:700}
dl{display:grid;grid-template-columns:170px 1fr;gap:10px}dd{margin:0;overflow-wrap:anywhere}
@media(max-width:600px){dl{grid-template-columns:1fr}}
</style></head><body><main>
<nav><a href="/itsm">ITSM humain (droits UNKNOWN)</a> · <a href="/demo/explore-story">Story ACME</a></nav>
<h1>Ticket GLPI simulé — ACME SAN → Payments</h1>
<p class="badge" data-simulation-badge="SIMULATED">SIMULATED · SANDBOX ONLY</p>
<p>Cette vue lit uniquement un ticket <code>SIM-GLPI-</code> issu du Core sandbox ACME-TEST.
Ce n'est ni GLPI réel, ni une permission humaine READ/READMY, ni une approbation LIVE.</p>
<section class="panel" aria-label="Lecture sandbox">
<label for="sim-attempt">Identifiant de tentative (ACME-SIM-…)</label>
<input id="sim-attempt" autocomplete="off" spellcheck="false" placeholder="ACME-SIM-…" maxlength="89">
<label for="sim-token">Jeton viewer (mémoire de cette page uniquement)</label>
<input id="sim-token" type="password" autocomplete="off">
<button id="sim-read" type="button">Lire le ticket simulé</button>
<button id="sim-clear" type="button">Effacer</button>
<p id="sim-status" role="status" aria-live="polite">UNKNOWN — aucun readback Core qualifié.</p>
</section>
<section class="panel" aria-labelledby="sim-ticket-title">
<h2 id="sim-ticket-title">Readback synthétique</h2>
<dl><dt>Ticket</dt><dd id="sim-ticket">UNKNOWN</dd>
<dt>État</dt><dd id="sim-state">UNKNOWN</dd>
<dt>Incident / Run</dt><dd id="sim-run">UNKNOWN</dd>
<dt>Transition</dt><dd id="sim-transition">UNKNOWN — historique non attesté</dd>
<dt>Provenance</dt><dd id="sim-provenance">UNKNOWN — aucune lecture</dd></dl>
</section>
<p><button type="button" disabled aria-disabled="true">Commenter dans GLPI réel</button>
<button type="button" disabled aria-disabled="true">Approuver humain</button></p>
<p>Le statut RESOLVED, lorsqu'il est affiché, vient d'un GET Core sandbox indépendant.
Il ne prouve pas la transition historique, ni le résultat E2E complet Core/Twin/Policy/Worker.
Aucune écriture GLPI, aucune action LIVE.</p>
</main><script src="/assets/acme-sim-glpi.js" defer></script></body></html>"""


def denied(code: int, reason: str):
    return JSONResponse({
        "schema": SCHEMA, "state": "UNAUTHORIZED" if code in (401, 403) else "UNKNOWN",
        "reason": reason, "simulated": True, "human_allow": False,
        "real_glpi_writes_allowed": False, "live_effects_allowed": False,
    }, status_code=code, headers={
        **HEADERS, **({"WWW-Authenticate": "Bearer"} if code == 401 else {}),
    })


def _core_sandbox_read(attempt_id: str) -> dict:
    """Only a fixed Core service origin and sandbox path; never GLPI itself."""
    token = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    base = os.getenv("CORE_URL", "http://aiops2-core:810").rstrip("/")
    parsed = urlsplit(base)
    if (not token or parsed.scheme not in ("http", "https")
            or parsed.hostname not in ("aiops2-core", "aiops2-rebuild-core", "127.0.0.1", "localhost")
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("core_sandbox_configuration_unavailable")
    try:
        response = requests.get(
            base + "/api/sandbox/acme/e2e/" + attempt_id,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            timeout=3, allow_redirects=False,
        )
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError("core_sandbox_readback_unavailable")
        data = response.json()
        if type(data) is not dict:
            raise ValueError("core_sandbox_readback_unqualified")
        return data
    except (requests.RequestException, ValueError, TypeError):
        raise ValueError("core_sandbox_readback_unavailable") from None


def _project(value: dict, attempt_id: str) -> dict:
    """A 200, a ticket-shaped JSON, or a forged ALLOW never qualifies itself."""
    expected = {
        "attempt_id": attempt_id, "tenant_id": TENANT,
        "source": "SYNTHETIC_SIMULATOR",
        "ticket_authority": "SIMULATED_ONLY", "ticket_status": "RESOLVED",
        "incident_status": "RESOLVED", "run_status": "RESOLVED",
        "analysis_validated": True, "critic_validated": True,
    }
    if any(type(value.get(k)) is not type(v) or value.get(k) != v for k, v in expected.items()):
        raise ValueError("core_sandbox_readback_unqualified")
    if (value.get("scenario_id", SCENARIO) != SCENARIO
            or value.get("mode", "SIMULATION") != "SIMULATION"
            or value.get("glpi_mode", "SIMULATED_ONLY") != "SIMULATED_ONLY"
            or value.get("approval_issuer", "TWIN_ACME_SIMULATED") != "TWIN_ACME_SIMULATED"):
        raise ValueError("core_sandbox_readback_unqualified")
    if any(value.get(k) not in (None, False) for k in (
        "human_allow", "human_approved", "human_approval_claimed", "glpi_write_enabled",
        "real_glpi_writes_allowed", "live_effects_allowed", "execution_allowed", "effect_allowed",
    )):
        raise ValueError("core_sandbox_readback_unqualified")
    if type(value.get("evidence_count")) is not int or value["evidence_count"] < 2:
        raise ValueError("core_sandbox_readback_unqualified")
    ids = {k: value.get(k) for k in ("incident_id", "run_id", "ticket_id")}
    if (not all(type(v) is str and IDENTIFIER.fullmatch(v) for v in ids.values())
            or not ids["ticket_id"].startswith("SIM-GLPI-")
            or ids["incident_id"].startswith("SIM-GLPI-")
            or ids["run_id"].startswith("SIM-GLPI-")):
        raise ValueError("core_sandbox_readback_unqualified")
    return {
        "schema": SCHEMA, "state": "RESOLVED", "simulated": True,
        "tenant_id": TENANT, "attempt_id": attempt_id,
        "scenario_id": SCENARIO, "mode": "SIMULATION",
        "ticket": {"id": ids["ticket_id"], "status": "RESOLVED",
                   "transition_to": "RESOLVED", "transition_history_attested": False},
        "incident_id": ids["incident_id"], "run_id": ids["run_id"],
        "provenance": "SIMULATED", "readback_source": "CORE_SANDBOX_READBACK",
        "source_freshness": "UNKNOWN", "observed_at": None,
        "human_allow": False, "native_glpi_readmy_attested": False,
        "real_glpi_writes_allowed": False, "live_effects_allowed": False,
        "host_e2e_qualified": False,
    }


@router.get("/demo/acme-sim-glpi", response_class=HTMLResponse)
def simulated_glpi_page():
    return HTMLResponse(PAGE, headers=HEADERS)


@router.get("/assets/acme-sim-glpi.js")
def simulated_glpi_script():
    return FileResponse(Path(__file__).with_name("acme_sim_glpi_client.js"),
                        media_type="application/javascript", headers=HEADERS)


@router.get("/api/demo/acme-sim-glpi/{attempt_id}")
def simulated_glpi_readback(attempt_id: str, authorization: str | None = Header(default=None)):
    # Authenticate before even considering a Core sandbox business GET.
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return denied(exc.status_code, str(exc.detail))
    if not ATTEMPT.fullmatch(attempt_id):
        return denied(403, "SANDBOX_ATTEMPT_SCOPE_DENIED")
    if os.getenv("AIOPS_ACME_SANDBOX_ENABLED") != "true":
        return denied(503, "SANDBOX_DISABLED")
    try:
        return JSONResponse(_project(_core_sandbox_read(attempt_id), attempt_id),
                            headers=HEADERS)
    except ValueError:
        return denied(503, "CORE_SIMULATED_TICKET_NOT_ATTESTED")
