from typing import Literal
import os,hmac

from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel, Field

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
    critic_validated: bool
    redundancy_ok: bool
    evidence_fresh: bool = False
    preconditions_verified: bool = False
    fencing_verified: bool = False
    human_approved: bool = False


def evaluate(x: Decision) -> dict:
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
        if not x.evidence_fresh:
            return {"state":"BLOCKED","decision":"ENRICH",
                    "reason":"synthetic diagnostic lacks fresh current-state evidence"}
        if x.severity == "UNKNOWN":
            return {"state":"UNKNOWN","decision":"ENRICH",
                    "reason":"synthetic incident severity is still unknown"}
        if x.confidence < 0.65:
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
    return "aiops_policy_up 1\n"
