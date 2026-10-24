"""Read-only NOC routes to mount INSIDE the existing portal ASGI app.

No process, listener, scheduler or shadow data source is started here.
The host portal supplies the read model from its real incident pipeline.
"""
from __future__ import annotations
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

VALID_STATES={"OK","WARN","CRIT","UNKNOWN"}
SCHEMA="aiops-noc-runtime-readmodel-v1"

def validate_noc_runtime_snapshot(snapshot:dict)->dict:
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
    if ts.tzinfo is None or ts>datetime.now(timezone.utc):
        raise ValueError("invalid observation time")
    steps=snapshot.get("steps")
    if not isinstance(steps,list) or len(steps)>100:
        raise ValueError("invalid incident timeline")
    for step in steps:
        if not isinstance(step,dict) or step.get("state") not in VALID_STATES:
            raise ValueError("invalid timeline step")
        if not isinstance(step.get("name"),str) or not step["name"]:
            raise ValueError("missing step name")
    return snapshot

def create_noc_router(read_model:Callable[[],dict|None]):
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
            return validate_noc_runtime_snapshot(data)
        except (ValueError,KeyError,TypeError):
            raise HTTPException(status_code=503,detail="NOC data unavailable or unverified")
    @router.get("/api/platform/components")
    def platform_components():
        from demo.noc_platform_registry import build_portal_component_registry
        # Until the host portal supplies trustworthy health observations,
        # all components remain UNKNOWN and every route remains unmounted.
        return build_portal_component_registry()

    @router.get("/noc",response_class=HTMLResponse)
    def noc_dashboard():
        data=noc_state()
        esc=lambda text:html.escape(str(text),quote=True)
        rows="".join("<tr><td>"+esc(s["name"])+"</td><td>"+esc(s["state"])+"</td></tr>" for s in data["steps"])
        return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOC AIOps</title></head>
<body><h1>NOC AIOps · Lecture seule</h1><p>Source: RUNTIME_READMODEL</p><p>Incident: """+esc(data["incident_id"])+""" · Run: """+esc(data["run_id"])+"""</p>
<p>Observation UTC: """+esc(data["observed_at"])+"""</p><table><thead><tr><th>Étape</th><th>État</th></tr></thead><tbody>"""+rows+"""</tbody></table></body></html>"""
    return router
