"""ACME-TEST simulated GLPI ticket readback. Not native GLPI human authority.

This projection is isolated from /api/portal/itsm and never grants READ/READMY.
A successful response requires independently authenticated fixed-path Worker/Core/Worker
sandbox GETs and a Core post-Worker resolution fence. Neither an HTTP 200 nor a
Worker no-effect receipt alone proves a final Core transition.
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
<dt>Worker</dt><dd id="sim-worker">UNKNOWN — aucun reçu no-effect</dd>
<dt>Provenance</dt><dd id="sim-provenance">UNKNOWN — aucune lecture</dd></dl>
</section>
<p><button type="button" disabled aria-disabled="true">Commenter dans GLPI réel</button>
<button type="button" disabled aria-disabled="true">Approuver humain</button></p>
<p>Le statut RESOLVED exige un reçu Worker no-effect indépendant, un GET Core final
avec barrière de résolution post-Worker et un second GET Worker cohérent.
L'historique exact de transition reste NOT_ATTESTED; ce n'est pas un PASS E2E hôte.
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


def _sandbox_config(component: str) -> tuple[str, str]:
    """Preflight both trusted origins before issuing any business GET."""
    token = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    config = {
        "core": ("CORE_URL", "http://aiops2-core:810",
                 {"aiops2-core", "aiops2-rebuild-core", "127.0.0.1", "localhost"}),
        "worker": ("WORKER_URL", "http://aiops2-worker:815",
                   {"aiops2-worker", "aiops2-rebuild-worker", "127.0.0.1", "localhost"}),
    }
    env, default, hosts = config[component]
    base = os.getenv(env, default).rstrip("/")
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError:
        raise ValueError("sandbox_service_configuration_unavailable") from None
    if (not token or parsed.scheme not in ("http", "https")
            or parsed.hostname not in hosts or not port
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("sandbox_service_configuration_unavailable")
    return base, token


def _sandbox_read(component: str, attempt_id: str) -> dict:
    """Fixed service allowlist, bearer and GET only; never native GLPI."""
    base, token = _sandbox_config(component)
    try:
        response = requests.get(
            base + "/api/sandbox/acme/e2e/" + attempt_id,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            timeout=3, allow_redirects=False,
        )
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError("sandbox_readback_unavailable")
        data = response.json()
        if type(data) is not dict:
            raise ValueError("sandbox_readback_unqualified")
        return data
    except (requests.RequestException, ValueError, TypeError):
        raise ValueError("sandbox_readback_unavailable") from None


def _project(core: dict, worker: dict, attempt_id: str) -> dict:
    """Only final Core state *after* independently checked Worker no-effect."""
    expected = {
        "schema": "aiops.core-acme-sandbox-readback.v1",
        "attempt_id": attempt_id, "tenant_id": TENANT, "scenario_id": SCENARIO,
        "mode": "SIMULATION", "source": "SYNTHETIC_SIMULATOR",
        "ticket_authority": "SIMULATED_ONLY", "glpi_mode": "SIMULATED_ONLY",
        "ticket_status": "RESOLVED", "incident_status": "RESOLVED",
        "run_status": "RESOLVED", "analysis_validated": True,
        "critic_validated": True, "source_event_count": 7,
        "source_hashes_qualified": True, "approval_issuer": "TWIN_ACME_SIMULATED",
        # Core must independently verify the persisted Worker receipt and the
        # order of its own terminal transition. These fields are NOT present
        # in the old pre-causal Core producer; old 200s deliberately fail 503.
        "worker_receipt_verified": True,
        "resolution_after_worker_receipt": True,
        "approval_fresh_at_resolution": True,
        "approval_nonce_consumed": True,
        "approval_nonce_revoked": False,
    }
    if any(type(core.get(k)) is not type(v) or core.get(k) != v
           for k, v in expected.items()):
        raise ValueError("core_final_resolution_not_attested")
    # Core's canonical readback has no human_allow key; absence never grants it.
    if (core.get("human_allow") not in (None, False)
            or any(core.get(k) is not False for k in (
                "human_approved", "human_approval_claimed",
                "real_glpi_writes_allowed", "live_effects_allowed",
                "execution_allowed", "effect_allowed"))):
        raise ValueError("core_simulated_authority_unqualified")
    if type(core.get("evidence_count")) is not int or core["evidence_count"] < 2:
        raise ValueError("core_evidence_unqualified")
    if (type(core.get("source_event_ids")) is not list
            or len(core["source_event_ids"]) != 7
            or not all(type(x) is str and IDENTIFIER.fullmatch(x)
                       for x in core["source_event_ids"])
            or len(set(core["source_event_ids"])) != 7
            or type(core.get("request_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", core["request_sha256"]) is None):
        raise ValueError("core_source_provenance_unqualified")
    ids = {k: core.get(k) for k in (
        "incident_id", "run_id", "ticket_id", "proposal_id", "approval_id")}
    if (not all(type(v) is str and IDENTIFIER.fullmatch(v)
                for v in ids.values())
            or not ids["ticket_id"].startswith("SIM-GLPI-")
            or not ids["approval_id"].startswith("SIM-APP-")
            or ids["incident_id"].startswith("SIM-GLPI-")
            or ids["run_id"].startswith("SIM-GLPI-")):
        raise ValueError("core_identity_unqualified")
    worker_expected = {
        "schema": "aiops.worker-acme-simulated-no-effect.v1",
        "attempt_id": attempt_id, "tenant_id": TENANT,
        "incident_id": ids["incident_id"], "run_id": ids["run_id"],
        "proposal_id": ids["proposal_id"], "approval_id": ids["approval_id"],
        "approval_issuer": "TWIN_ACME_SIMULATED",
        "approval_kind": "SIMULATED", "action": "SIMULATE",
        "receipt_status": "SIMULATED_NO_EFFECT",
        "receipt_phase": "PRE_RESOLUTION",
        "core_status_at_validation": "PREPARED",
        "resolution_verified": False, "post_resolution_readback_required": True,
        "audit_authority": "TEMPORAL_WORKFLOW_HISTORY_ONLY",
        "effect_receipts": 0, "human_approved": False,
        "execution_allowed": False, "effect_allowed": False,
        "live_effects_allowed": False, "real_glpi_writes_allowed": False,
        "core_014_015_written": False, "glpi_write": False,
    }
    if any(type(worker.get(k)) is not type(v) or worker.get(k) != v
           for k, v in worker_expected.items()):
        raise ValueError("worker_receipt_not_attested")
    if worker.get("audit_transitions") != [
            "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
            "TWIN_SIMULATED_APPROVAL_VALIDATED",
            "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
            "WORKER_NO_EFFECT"]:
        raise ValueError("worker_audit_not_attested")
    return {
        "schema": SCHEMA, "state": "RESOLVED", "simulated": True,
        "tenant_id": TENANT, "attempt_id": attempt_id,
        "scenario_id": SCENARIO, "mode": "SIMULATION",
        "ticket": {"id": ids["ticket_id"], "status": "RESOLVED",
                   "current_state": "RESOLVED", "transition_history_attested": False},
        "incident_id": ids["incident_id"], "run_id": ids["run_id"],
        "worker_receipt_status": "SIMULATED_NO_EFFECT",
        "worker_receipt_phase": "PRE_RESOLUTION",
        "worker_no_effect_verified": True,
        "core_resolution_after_worker_verified": True,
        "provenance": "SIMULATED",
        "readback_source": "CORE_AND_WORKER_INDEPENDENT_SANDBOX_GET",
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
        # Worker receipt first; Core final state only after that independent GET.
        # Re-read Worker to fence a changing/replaced receipt across Core GET.
        _sandbox_config("core")
        _sandbox_config("worker")
        worker_before = _sandbox_read("worker", attempt_id)
        core_final = _sandbox_read("core", attempt_id)
        worker_after = _sandbox_read("worker", attempt_id)
        if worker_before != worker_after:
            raise ValueError("worker_receipt_rotated_during_core_read")
        return JSONResponse(_project(core_final, worker_after, attempt_id),
                            headers=HEADERS)
    except ValueError:
        return denied(503, "CORE_SIMULATED_TICKET_NOT_ATTESTED")
