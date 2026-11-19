"""Authenticated synthetic journey. Never grants actor/tenant or execution rights."""
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, Request
from portal.acme_demo_simulation_pipeline import run_acme_demo_simulation
from portal.portal_command_auth import require_demo_operator
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
            "timeline": [{"cue": step["cue"], "service": step["service"], "view": step["view"], "status": "MISSING"} for step in impact.get("checkpoint_evidence", [])],
            "twin": impact.get("twin_consumer"),
            "affected_cis": impact.get("affected_cis", []),
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
    return explore_story_control(payload=payload, authorization=authorization)

@router.get("/rag")
def rag(asset: str | None = None, authorization: str | None = Header(default=None)):
    return noc_demo_rag(asset=asset, authorization=authorization)

@router.get("/run/{rid}")
def run(rid: str, authorization: str | None = Header(default=None)):
    return run_detail_api(rid=rid, authorization=authorization)

@router.get("/glpi")
def glpi(authorization: str | None = Header(default=None)):
    return glpi_readonly_status(authorization=authorization)

@router.post("/commands/{command}")
def blocked_command(command: str, authorization: str | None = Header(default=None)):
    _require_portal_read_auth(authorization)
    if command not in BLOCKED:
        raise HTTPException(404, "unknown_command")
    return _noc_json_response({
        "state": "BLOCKED", "reason": "AUTHORIZED_RUNTIME_CONTRACT_NOT_QUALIFIED",
        "runtime_attested": False, "live_remediation_authorized": False,
    }, status_code=503)


@router.post("/demo/simulation")
async def simulation(request: Request, authorization: str | None = Header(default=None)):
    """Only the distinct DEMO operator may invoke the offline pipeline."""
    try:
        require_demo_operator(authorization)
    except HTTPException as exc:
        return _noc_json_response({"state": "BLOCKED", "reason": exc.detail}, status_code=exc.status_code)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, "invalid_simulation_context")
    if (type(payload) is not dict or set(payload) != {"incident_id", "run_id", "source_sha256"}
            or any(type(v) is not str for v in payload.values())):
        raise HTTPException(422, "invalid_simulation_context")
    try:
        impact = _load_or_503()
        if any(payload[k] != impact[k] for k in payload):
            raise HTTPException(409, "simulation_context_mismatch")
        result = run_acme_demo_simulation()
        if (result["incident_id"] != payload["incident_id"]
                or result["source_sha256"] != payload["source_sha256"]
                or result["mode"] != "DEMO"
                or result["actual_recovery_state"] != "UNKNOWN"
                or any(result[k] is not False for k in (
                    "runtime_execution_performed", "glpi_write_performed",
                    "temporal_execution_performed", "live_remediation_authorized"))):
            raise ValueError("unqualified_simulation_result")
        simulation = result["simulation"]
        receipt = simulation["receipt"]
        digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if (digest != simulation["receipt_sha256"]
                or receipt["incident_id"] != payload["incident_id"]
                or receipt["mode"] != "DEMO"
                or receipt["simulation_result"] != "HYPOTHETICAL_ONLY"
                or any(receipt[k] is not False for k in (
                    "runtime_execution_verified", "independent_postcheck_verified",
                    "temporal_execution_verified", "itil_transition_authorized", "live_remediation_authorized"))
                or result["evidence_gate"]["itil_transition_authorized"] is not False
                or result["evidence_gate"]["live_remediation_authorized"] is not False):
            raise ValueError("unqualified_simulation_receipt")
        return _noc_json_response({**result, "run_id": payload["run_id"]})
    except (ValueError, KeyError, TypeError, OSError):
        raise HTTPException(503, "simulation_unqualified")
