from typing import Literal
import os,hmac

from fastapi import FastAPI,Header,HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, StrictBool
try:
    from policy import autonomy_store, execution_fence
except ModuleNotFoundError:
    from app.policy import autonomy_store, execution_fence

app = FastAPI(title="ACME Policy Engine", version="2.2.0")
INTERNAL_TOKEN=os.getenv("AIOPS_INTERNAL_TOKEN","")


def authorize(authorization):
    if not INTERNAL_TOKEN:
        raise HTTPException(503,"internal_auth_not_configured")
    supplied=(authorization or "").removeprefix("Bearer ")
    if not supplied or not hmac.compare_digest(supplied,INTERNAL_TOKEN):
        raise HTTPException(401,"invalid_internal_token")


class Decision(BaseModel):
    mode: Literal["LIVE", "DEMO", "REPLAY", "STORY"]
    command: Literal["OBSERVE", "ENRICH", "EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"]
    severity: Literal["P1", "P2", "P3", "P4", "UNKNOWN"]
    confidence: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=0)
    # Deliberately required: callers must not inherit a trusted default.
    critic_validated: StrictBool
    redundancy_ok: StrictBool
    evidence_fresh: StrictBool = False
    preconditions_verified: bool = False
    fencing_verified: bool = False
    human_approved: bool = False
    freeze_active: bool | None = None
    management_exception_verified: bool = False
    change_approval_verified: bool = False
    operation_class: Literal["OBSERVATION","ROUTINE_PREAPPROVED","STANDARD_CHANGE","EXCEPTIONAL_CHANGE","AUTONOMOUS_REMEDIATION"] = "AUTONOMOUS_REMEDIATION"


def evaluate(x: Decision) -> dict:
    effect = x.command in ("EXECUTE", "RESOLVE", "REMEDIATE")
    persisted=autonomy_store.status()
    autonomy_mode=persisted["mode"]
    if not persisted["healthy"]:
        return {"state":"BLOCKED","decision":"ESCALATE","reason":"AUTONOMY_STATE_UNAVAILABLE"}
    if autonomy_mode not in ("NORMAL", "FREEZE", "STOP_AUTO"):
        return {"state":"BLOCKED","decision":"ESCALATE","reason":"INVALID_AUTONOMY_MODE"}
    if effect and autonomy_mode == "STOP_AUTO" and x.operation_class == "AUTONOMOUS_REMEDIATION":
        return {"state":"BLOCKED","decision":"ESCALATE","reason":"AUTONOMOUS_REMEDIATION_SUSPENDED"}
    if effect and autonomy_mode == "FREEZE" and x.operation_class not in ("ROUTINE_PREAPPROVED","STANDARD_CHANGE"):
        return {"state":"BLOCKED","decision":"HUMAN_APPROVAL","reason":"FREEZE_RESTRICTS_OPERATION_CLASS"}
    if effect and x.operation_class in ("ROUTINE_PREAPPROVED","STANDARD_CHANGE") and not x.preconditions_verified:
        return {"state":"BLOCKED","decision":"HUMAN_APPROVAL","reason":"PREAPPROVED_OPERATION_NOT_VERIFIED"}
    if effect and os.getenv("AIOPS_POLICY_EMERGENCY_STOP", "true").lower() != "false":
        return {"state":"BLOCKED","decision":"ESCALATE",
                "reason":"EMERGENCY_STOP_ACTIVE: effect prohibited"}
    if effect and x.freeze_active is None:
        return {"state":"BLOCKED","decision":"HUMAN_APPROVAL",
                "reason":"FREEZE_STATUS_UNKNOWN: effect prohibited"}
    if effect and x.freeze_active and not (x.management_exception_verified and x.change_approval_verified):
        return {"state":"BLOCKED","decision":"HUMAN_APPROVAL",
                "reason":"CHANGE_FREEZE_ACTIVE: management exception and Change approval required"}
    # Severity is an independent safety signal: never downgrade P1 to UNKNOWN
    # or ALLOW merely because evidence is missing or confidence is high.
    if x.mode == "LIVE" and x.severity == "P1":
        return {
            "state": "BLOCKED",
            "decision": "ESCALATE",
            "reason": "P1 incidents require escalation; autonomous execution is prohibited",
        }

    if x.evidence_count == 0:
        return {
            "state": "UNKNOWN",
            "decision": "HUMAN_APPROVAL",
            "reason": "no evidence available",
        }

    # Even a simulation must not present unsupported AI claims as an approved
    # diagnostic. DEMO/REPLAY/STORY can skip *effect* preconditions, never
    # evidence integrity or independent review.
    if x.mode in ("DEMO", "REPLAY", "STORY"):
        if not x.critic_validated:
            return {"state":"BLOCKED","decision":"HUMAN_APPROVAL",
                    "reason":"synthetic diagnostic rejected or not validated by independent critic"}
        if not x.redundancy_ok:
            return {"state":"BLOCKED","decision":"HUMAN_APPROVAL",
                    "reason":"synthetic redundancy or safety check failed"}
        if not x.evidence_fresh:
            return {"state":"BLOCKED","decision":"ENRICH",
                    "reason":"synthetic diagnostic lacks fresh current-state evidence"}
        if x.severity == "UNKNOWN":
            return {"state":"UNKNOWN","decision":"ENRICH",
                    "reason":"synthetic incident severity is still unknown"}
        if x.confidence < 0.90:
            return {"state":"BLOCKED","decision":"ENRICH",
                    "reason":"synthetic diagnostic confidence below qualification threshold"}
        return {
            "state": "PASS",
            "decision": "SIMULATE",
            "reason": "critic validated and evidence fresh; no production mutation permitted",
        }

    if x.severity == "UNKNOWN":
        return {"state":"UNKNOWN","decision":"HUMAN_APPROVAL",
                "reason":"LIVE incident severity is unknown; enrich before action"}

    if not x.critic_validated:
        reason = "critic validation is missing or failed"
    elif not x.evidence_fresh:
        reason = "evidence freshness has not been verified"
    elif not x.preconditions_verified:
        reason = "action preconditions have not been verified"
    elif not x.fencing_verified:
        reason = "ownership/fencing has not been verified"
    elif x.command in ("EXECUTE", "RESOLVE", "REMEDIATE") and not x.human_approved:
        reason = "explicit human approval is required for a live effect"
    elif not x.redundancy_ok:
        reason = "redundancy/safety checks failed"
    elif x.confidence < 0.90:
        reason = "confidence threshold not met"
    else:
        # No qualified LIVE effect executor, ownership lease, fencing validation,
        # independently bound human-approval proof or reconciliation workflow
        # exists yet. The caller's booleans cannot activate an effect.
        if x.command in ("EXECUTE","RESOLVE","REMEDIATE"):
            return {
                "state": "BLOCKED",
                "decision": "HUMAN_APPROVAL",
                "reason": "LIVE_EFFECTS_NOT_QUALIFIED: real effect adapters and fencing are disabled",
            }
        return {
            "state": "PASS",
            "decision": "ALLOW",
            "reason": "read-only live disposition satisfied; no effect permitted",
        }

    return {"state": "BLOCKED", "decision": "HUMAN_APPROVAL", "reason": reason}


@app.get("/health")
def health():
    return {"status": "ok", "component": "policy", "fail_closed": True}


@app.post("/api/policy/check")
def check(x: Decision,authorization: str|None=Header(default=None)):
    authorize(authorization)
    return evaluate(x)


@app.get("/metrics")
def metrics():
    return PlainTextResponse('aiops_policy_up 1\n', media_type='text/plain; version=0.0.4')


class ModeChange(BaseModel):
    mode: Literal["NORMAL","FREEZE","STOP_AUTO"]
    actor: str = Field(min_length=1,max_length=128)
    reason: str = Field(min_length=12,max_length=1024)
    expected_revision: int = Field(ge=0)

@app.get("/api/policy/autonomy")
def autonomy_read(authorization: str|None=Header(default=None)):
    authorize(authorization)
    return autonomy_store.status()

@app.get("/api/policy/autonomy/history")
def autonomy_history(authorization: str|None=Header(default=None)):
    authorize(authorization)
    try: return {"items":autonomy_store.history()}
    except Exception: raise HTTPException(503,"policy_state_unavailable")

@app.post("/api/policy/autonomy")
def autonomy_change(x:ModeChange,authorization: str|None=Header(default=None)):
    authorize(authorization)
    # Internal token alone is not sufficient to establish a management authorization.
    # Conservative MVP: only tightening to STOP_AUTO is supported via API.
    if x.mode!="STOP_AUTO": raise HTTPException(403,"relaxation_requires_independent_admin_authorization")
    try: return autonomy_store.set_mode(x.mode,x.actor,x.reason,x.expected_revision)
    except RuntimeError: raise HTTPException(409,"revision_conflict")
    except (OSError,ValueError): raise HTTPException(503,"policy_state_unavailable")

class SimulationAdmission(BaseModel):
    operation_id: str = Field(min_length=1,max_length=128)
    expected_revision: int = Field(ge=0)
    operation_class: Literal["ROUTINE_PREAPPROVED","STANDARD_CHANGE","AUTONOMOUS_REMEDIATION"]

@app.post("/api/policy/simulation/reserve")
def simulation_reserve(x:SimulationAdmission,authorization: str|None=Header(default=None)):
    authorize(authorization)
    result=execution_fence.reserve(x.operation_id,x.expected_revision,x.operation_class)
    return {**result,"scope":"SIMULATION_ONLY","execution_allowed":False}

@app.get("/api/policy/simulation/summary")
def simulation_summary(authorization: str|None=Header(default=None)):
    authorize(authorization)
    return execution_fence.summary()

@app.get("/api/policy/simulation/decisions")
def simulation_decisions(authorization: str|None=Header(default=None)):
    authorize(authorization)
    try: return {"scope":"SIMULATION_ONLY","items":execution_fence.decisions()}
    except Exception: raise HTTPException(503,"policy_audit_unavailable")
