"""Authenticated synthetic journey. Never grants actor/tenant or execution rights."""
from fastapi import APIRouter, Header, HTTPException, Request
from portal.noc_runtime import _require_portal_read_auth, _noc_json_response
from portal.acme_impact_read_model import _load_or_503
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_explore_story import explore_story_control
from portal.noc_demo_rag import noc_demo_rag
from portal.glpi_operator_view import glpi_readonly_status
from portal.acme_run_detail import run_detail_api

router = APIRouter(prefix="/api/mission-actions", tags=["mission-actions"])
BLOCKED = ("fs-create", "fs-execute", "fs-recover", "demo-execute",
           "analyst-inference", "critic-inference", "policy-evaluate",
           "hitl-decide", "temporal-start", "temporal-inspect", "evidence-runtime")

@router.get("/session")
def session(authorization: str | None = Header(default=None)):
    _require_portal_read_auth(authorization)
    return _noc_json_response({
        "session_kind": "SHARED_VIEWER", "tenant_acl_qualified": False,
        "mode": "DEMO", "live_remediation_authorized": False,
        "available": ["journey", "story", "rag", "run", "glpi"],
        "blocked": list(BLOCKED),
    })

@router.get("/journey")
def journey(authorization: str | None = Header(default=None)):
    _require_portal_read_auth(authorization)
    try:
        impact = _load_or_503()
        cockpit = project_synthetic_incident_cockpit(impact)
        return _noc_json_response({
            "schema": "aiops.mission-actions.journey.v1",
            "scenario_id": "acme-san-payments", "run_id": impact["run_id"],
            "incident_id": impact["incident_id"], "source_sha256": impact["source_sha256"],
            "affected_ci_ids": impact["affected_ci_ids"],
            "mode": "DEMO", "runtime_attested": False,
            "live_remediation_authorized": False, "cockpit": cockpit,
            "decision_preview": impact["decision_preview"],
        })
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "synthetic_journey_unqualified")

@router.post("/story")
async def story(request: Request, authorization: str | None = Header(default=None)):
    _require_portal_read_auth(authorization)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, "invalid_story_control")
    return explore_story_control(payload, authorization)

@router.get("/rag")
def rag(asset: str | None = None, authorization: str | None = Header(default=None)):
    return noc_demo_rag(asset, authorization)

@router.get("/run/{rid}")
def run(rid: str, authorization: str | None = Header(default=None)):
    return run_detail_api(rid, authorization)

@router.get("/glpi")
def glpi(authorization: str | None = Header(default=None)):
    return glpi_readonly_status(authorization)

@router.post("/commands/{command}")
def blocked_command(command: str, authorization: str | None = Header(default=None)):
    _require_portal_read_auth(authorization)
    if command not in BLOCKED:
        raise HTTPException(404, "unknown_command")
    return _noc_json_response({
        "state": "BLOCKED", "reason": "AUTHORIZED_RUNTIME_CONTRACT_NOT_QUALIFIED",
        "runtime_attested": False, "live_remediation_authorized": False,
    }, status_code=503)
