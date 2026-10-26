"""Read-only NOC routes to mount INSIDE the existing portal ASGI app.

No process, listener, scheduler or shadow data source is started here.
The host portal supplies the read model from its real incident pipeline.
"""
from __future__ import annotations
from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any
from demo.star_n8n_identity_gate import IDENTIFIER, verify_handoff

VALID_STATES={"OK","WARN","CRIT","UNKNOWN"}
SCHEMA="aiops-noc-runtime-readmodel-v1"

def validate_noc_runtime_snapshot(snapshot:dict, *, now_utc:str|None=None, max_age_seconds:int=300)->dict:
    """Validate a fresh authenticated read model, never an old replay as live NOC."""
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600:
        raise ValueError("invalid NOC freshness policy")
    if now_utc is None:
        now = datetime.now(timezone.utc)
    else:
        if not isinstance(now_utc,str) or not now_utc.endswith("Z"):
            raise ValueError("invalid NOC clock")
        try:
            now = datetime.fromisoformat(now_utc.replace("Z","+00:00"))
        except ValueError as exc:
            raise ValueError("invalid NOC clock") from exc
    if not isinstance(snapshot,dict) or snapshot.get("schema")!=SCHEMA:
        raise ValueError("missing runtime read model")
    if snapshot.get("provenance")!="RUNTIME_READMODEL" or snapshot.get("runtime_authenticated") is not True:
        raise ValueError("runtime source not authenticated")
    if snapshot.get("live_remediation_authorized") is not False:
        raise ValueError("read-only NOC boundary violated")
    if not isinstance(snapshot.get("run_id"),str) or not snapshot["run_id"]:
        raise ValueError("missing run correlation")
    if not isinstance(snapshot.get("incident_id"),str) or not snapshot["incident_id"]:
        raise ValueError("missing incident identity")
    observed=snapshot.get("observed_at")
    if not isinstance(observed,str) or not observed.endswith("Z"):
        raise ValueError("missing UTC timestamp")
    try:
        ts=datetime.fromisoformat(observed.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if ts.tzinfo is None or not 0 <= (now-ts).total_seconds() <= max_age_seconds:
        raise ValueError("stale or future NOC observation")
    # Optional correlation is a host claim, not capture provenance proof.
    ticket_id = snapshot.get("ticket_id")
    if ticket_id is not None and (not isinstance(ticket_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", ticket_id) is None):
        raise ValueError("invalid ticket correlation")
    evidence_sha256 = snapshot.get("evidence_sha256")
    if evidence_sha256 is not None and (not isinstance(evidence_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None):
        raise ValueError("invalid evidence digest")
    if snapshot.get("evidence_runtime_attested", False) is not False:
        raise ValueError("unverified evidence attestation claim")
    # Reuse the existing 02->03 identity gate. Consistency is NOT runtime proof.
    if snapshot.get("handoff_runtime_authenticated", False) is not False:
        raise ValueError("unsupported handoff runtime attestation")
    correlation_id = snapshot.get("correlation_id")
    if correlation_id is not None and (not isinstance(correlation_id, str)
            or IDENTIFIER.fullmatch(correlation_id) is None):
        raise ValueError("invalid canonical correlation")
    if "handoff_02_03" in snapshot:
        if correlation_id is None:
            raise ValueError("missing correlation for 02->03 handoff")
        try:
            handoff = verify_handoff(snapshot["handoff_02_03"])
        except ValueError:
            raise ValueError("invalid 02->03 handoff") from None
        if (handoff["run_id"] != snapshot["run_id"]
                or handoff["incident_id"] != snapshot["incident_id"]
                or handoff["correlation_id"] != correlation_id):
            raise ValueError("02->03 identity contradicts NOC incident")
    steps=snapshot.get("steps")
    if not isinstance(steps,list) or len(steps)>100:
        raise ValueError("invalid incident timeline")
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("invalid timeline step")
        state = step.get("state")
        # JSON arrays/objects are unhashable: type-check before set membership so
        # malformed provider data is a controlled contract rejection, not TypeError.
        if not isinstance(state, str) or state not in VALID_STATES:
            raise ValueError("invalid timeline step")
        if not isinstance(step.get("name"),str) or not step["name"]:
            raise ValueError("missing step name")
    return snapshot

def public_noc_snapshot(snapshot:dict, *, now_utc:str|None=None, max_age_seconds:int=300)->dict:
    """Project only reviewed NOC fields; never expose provider-private metadata."""
    verified = validate_noc_runtime_snapshot(
        snapshot, now_utc=now_utc, max_age_seconds=max_age_seconds)
    handoff = (verify_handoff(verified["handoff_02_03"])
               if "handoff_02_03" in verified else None)
    return {
        "schema": SCHEMA,
        "provenance": "RUNTIME_READMODEL",
        "runtime_authenticated": True,
        "live_remediation_authorized": False,
        "run_id": verified["run_id"],
        "incident_id": verified["incident_id"],
        "correlation_id": verified.get("correlation_id"),
        "handoff_status": ("CONSISTENT_UNAUTHENTICATED" if handoff else "ABSENT"),
        "handoff_identity_sha256": (handoff["identity_sha256"] if handoff else None),
        "handoff_runtime_authenticated": False,
        "ticket_id": verified.get("ticket_id"),
        "evidence_sha256": verified.get("evidence_sha256"),
        "evidence_status": ("UNVERIFIED_DIGEST" if verified.get("evidence_sha256")
                            else "ABSENT"),
        "evidence_runtime_attested": False,
        "observed_at": verified["observed_at"],
        "steps": [{"name": step["name"], "state": step["state"]}
                  for step in verified["steps"]],
    }

def public_component_registry(component_observations:Callable[[],dict|None]|None=None, *, now_utc:str|None=None)->dict:
    """Expose only validated, fresh host observations; never infer route mounting.

    No provider means UNKNOWN for all components. A configured provider that
    fails or returns malformed data must not silently become a healthy view.
    """
    from demo.noc_platform_registry import build_portal_component_registry
    if component_observations is None:
        return build_portal_component_registry(now_utc=now_utc)
    if not callable(component_observations):
        raise ValueError("invalid component observation provider")
    observations=component_observations()
    if not isinstance(observations,dict):
        raise ValueError("component observations unavailable")
    return build_portal_component_registry(observations,now_utc=now_utc)

def render_noc_dashboard(view:dict, registry:dict)->str:
    """Show the 20-component convergence inventory without claiming mounted routes."""
    from demo.noc_platform_registry import COMPONENTS
    from html import escape
    if (not isinstance(view,dict) or view.get("schema")!=SCHEMA
            or view.get("provenance")!="RUNTIME_READMODEL"
            or view.get("runtime_authenticated") is not True
            or view.get("live_remediation_authorized") is not False
            or view.get("evidence_runtime_attested") is not False
            or view.get("handoff_runtime_authenticated") is not False):
        raise ValueError("unverified NOC dashboard source")
    handoff_status = view.get("handoff_status")
    handoff_digest = view.get("handoff_identity_sha256")
    if (handoff_status not in ("ABSENT", "CONSISTENT_UNAUTHENTICATED")
            or (handoff_status == "ABSENT" and handoff_digest is not None)
            or (handoff_status != "ABSENT" and (
                not isinstance(handoff_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", handoff_digest) is None
                or not view.get("correlation_id")))):
        raise ValueError("unverified 02->03 handoff claim")
    if (not isinstance(registry,dict)
            or registry.get("schema")!="aiops-single-portal-component-registry-v1"
            or registry.get("live_remediation_authorized") is not False
            or not isinstance(registry.get("items"),list)
            or len(registry["items"])!=len(COMPONENTS)):
        raise ValueError("invalid portal component inventory")
    component_rows=[]
    for item,(ident,label,path,category) in zip(registry["items"],COMPONENTS):
        if (not isinstance(item,dict) or item.get("id")!=ident
                or item.get("name")!=label or item.get("path")!=path
                or item.get("category")!=category
                or not isinstance(item.get("state"), str)
                or item.get("state") not in VALID_STATES
                or item.get("available_in_portal") is not False
                or item.get("requires_route_integration") is not True):
            raise ValueError("contradictory or unattested component route")
        component_rows.append(
            '<tr class="component-row"><td>'+escape(label,quote=True)
            +'</td><td>'+escape(path,quote=True)
            +'</td><td>'+escape(item["state"],quote=True)
            +'</td><td>NON ATTESTÉE</td></tr>')
    esc=lambda value:escape(str(value),quote=True)
    steps="".join('<tr><td>'+esc(s["name"])+'</td><td>'+esc(s["state"])+'</td></tr>'
                  for s in view["steps"])
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>NOC AIOps · Convergence</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;'
        'padding:0 1rem;color:#182233}table{border-collapse:collapse;width:100%;'
        'margin:1rem 0 2rem}th,td{border:1px solid #ccd4df;padding:.5rem;'
        'text-align:left}th{background:#edf2f8}.warning{background:#fff4d6;'
        'padding:1rem;border-left:4px solid #b7791f}</style></head><body>'
        '<h1>NOC AIOps · Lecture seule</h1>'
        '<p class="warning">Source RUNTIME_READMODEL déclarée par le fournisseur ; '
        'authentification cryptographique et routes runtime NON ATTESTÉES. '
        'Aucune remédiation LIVE.</p>'
        '<p>Incident: '+esc(view["incident_id"])+' · Run: '+esc(view["run_id"])+'</p>'
        '<p>Corrélation: '+esc(view["correlation_id"] or "ABSENT")+'</p>'
        '<p>Handoff n8n 02→03: '+esc(handoff_status)
        +' · SHA-256 identité: '+esc(handoff_digest or "ABSENT")
        +' (cohérence uniquement, exécution non authentifiée)</p>'
        '<p>Ticket: '+esc(view["ticket_id"] or "ABSENT")+'</p>'
        '<p>Evidence SHA-256 (non vérifié): '+esc(view["evidence_sha256"] or "ABSENT")
        +' · '+esc(view["evidence_status"])+'</p>'
        '<p>Observation UTC: '+esc(view["observed_at"])+'</p>'
        '<h2>Chronologie incident</h2><table><thead><tr><th>Étape</th><th>État</th>'
        '</tr></thead><tbody>'+steps+'</tbody></table>'
        '<h2>Convergence des '+str(len(COMPONENTS))+' composants</h2>'
        '<p>Chemins planifiés uniquement, aucun lien activé sans attestation '
        'indépendante du montage et de l’authentification.</p>'
        '<table><thead><tr><th>Composant</th><th>Chemin prévu</th>'
        '<th>Santé déclarée</th><th>Route</th></tr></thead><tbody>'
        +''.join(component_rows)+'</tbody></table></body></html>'
    )

def create_noc_router(read_model:Callable[[],dict|None],
                      component_observations:Callable[[],dict|None]|None=None):
    """Mount via existing_app.include_router(...); uses caller's auth middleware."""
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import HTMLResponse
    import html
    router=APIRouter()
    @router.get("/api/noc/state")
    def noc_state():
        try:
            data=read_model()
            if data is None:
                raise ValueError("NOC runtime data unavailable")
            return public_noc_snapshot(data)
        except Exception:
            # Fail closed on provider outages and unexpected provider errors.
            # Never return exception text, tokens or raw upstream payloads.
            raise HTTPException(status_code=503,detail="NOC data unavailable or unverified")
    @router.get("/api/platform/components")
    def platform_components():
        try:
            # Host-supplied read-only health only. Route availability remains
            # false until separately attested by the existing portal.
            return public_component_registry(component_observations)
        except Exception:
            raise HTTPException(status_code=503,
                                detail="Component observations unavailable or unverified")

    @router.get("/noc",response_class=HTMLResponse)
    def noc_dashboard():
        try:
            return render_noc_dashboard(noc_state(), platform_components())
        except Exception:
            raise HTTPException(status_code=503,
                                detail="NOC dashboard unavailable or unverified")
    return router
