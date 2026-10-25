"""Read-only NOC routes to mount INSIDE the existing portal ASGI app.

No process, listener, scheduler or shadow data source is started here.
The host portal supplies the read model from its real incident pipeline.
"""
from __future__ import annotations
from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any

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
    steps=snapshot.get("steps")
    if not isinstance(steps,list) or len(steps)>100:
        raise ValueError("invalid incident timeline")
    for step in steps:
        if not isinstance(step,dict) or step.get("state") not in VALID_STATES:
            raise ValueError("invalid timeline step")
        if not isinstance(step.get("name"),str) or not step["name"]:
            raise ValueError("missing step name")
    return snapshot

def public_noc_snapshot(snapshot:dict, *, now_utc:str|None=None, max_age_seconds:int=300)->dict:
    """Project only reviewed NOC fields; never expose provider-private metadata."""
    verified = validate_noc_runtime_snapshot(
        snapshot, now_utc=now_utc, max_age_seconds=max_age_seconds)
    return {
        "schema": SCHEMA,
        "provenance": "RUNTIME_READMODEL",
        "runtime_authenticated": True,
        "live_remediation_authorized": False,
        "run_id": verified["run_id"],
        "incident_id": verified["incident_id"],
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
        data=noc_state()
        esc=lambda text:html.escape(str(text),quote=True)
        rows="".join("<tr><td>"+esc(s["name"])+"</td><td>"+esc(s["state"])+"</td></tr>" for s in data["steps"])
        return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOC AIOps</title></head>
<body><h1>NOC AIOps · Lecture seule</h1><p>Source: RUNTIME_READMODEL</p><p>Incident: """+esc(data["incident_id"])+""" · Run: """+esc(data["run_id"])+"""</p>
<p>Ticket: """+esc(data["ticket_id"] or "ABSENT")+"""</p>
<p>Evidence SHA-256 (unverified): """+esc(data["evidence_sha256"] or "ABSENT")+"""</p>
<p>Evidence status: """+esc(data["evidence_status"])+"""</p>
<p>Observation UTC: """+esc(data["observed_at"])+"""</p><table><thead><tr><th>Étape</th><th>État</th></tr></thead><tbody>"""+rows+"""</tbody></table></body></html>"""
    return router
