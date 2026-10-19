from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="ACME Policy Engine", version="2.1.0")


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
    if x.evidence_count == 0:
        return {
            "state": "UNKNOWN",
            "decision": "HUMAN_APPROVAL",
            "reason": "no evidence available",
        }

    if x.mode in ("DEMO", "REPLAY", "STORY"):
        return {
            "state": "PASS",
            "decision": "SIMULATE",
            "reason": "synthetic mode: no production mutation permitted",
        }

    # P1 is never auto-authorized, regardless of model confidence.
    if x.severity == "P1":
        return {
            "state": "BLOCKED",
            "decision": "ESCALATE",
            "reason": "P1 incidents require escalation; autonomous execution is prohibited",
        }

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
        return {
            "state": "PASS",
            "decision": "ALLOW",
            "reason": "required evidence, approval and safety checks are satisfied",
        }

    return {"state": "BLOCKED", "decision": "HUMAN_APPROVAL", "reason": reason}


@app.get("/health")
def health():
    return {"status": "ok", "component": "policy", "fail_closed": True}


@app.post("/api/policy/check")
def check(x: Decision):
    return evaluate(x)


@app.get("/metrics")
def metrics():
    return "aiops_policy_up 1\\n"
