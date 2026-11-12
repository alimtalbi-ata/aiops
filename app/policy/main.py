from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="ACME Policy Engine", version="2.1.0")

# Mutating LIVE commands require an independently verified, bound HITL receipt.
# The current boolean human_approved is not such a receipt.
LIVE_EFFECT_COMMANDS = frozenset({"EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"})


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


def _evaluate_decision(x: Decision) -> dict:
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

    if x.mode in ("DEMO", "REPLAY", "STORY"):
        return {
            "state": "PASS",
            "decision": "SIMULATE",
            "reason": "synthetic mode: no production mutation permitted",
        }

    if not x.critic_validated:
        reason = "critic validation is missing or failed"
    elif not x.evidence_fresh:
        reason = "evidence freshness has not been verified"
    elif not x.preconditions_verified:
        reason = "action preconditions have not been verified"
    elif not x.fencing_verified:
        reason = "ownership/fencing has not been verified"
    elif x.command in LIVE_EFFECT_COMMANDS and not x.human_approved:
        reason = "explicit human approval is required for a live effect"
    elif x.command in LIVE_EFFECT_COMMANDS:
        # Fail closed: no authenticated, expiring, one-use approval binding is
        # validated here. A caller-controlled boolean must never permit effects.
        reason = "LIVE effect requires authenticated one-use HITL binding to incident/run/recipe/target/params"
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


def evaluate(x: Decision) -> dict:
    """Expose a non-authorizing Policy verdict on every path.

    PASS/ALLOW can describe a read-only policy check, never an effect grant.
    Core HITL, OIDC, fencing and executor authorization are separate gates.
    """
    verdict = _evaluate_decision(x)
    return {**verdict, "execution_allowed": False, "effect_allowed": False}


@app.get("/health")
def health():
    return {"status": "ok", "component": "policy", "fail_closed": True}


@app.post("/api/policy/check")
def check(x: Decision):
    # Preserve the v2.1 three-field HTTP contract consumed by the existing
    # strict Core read-only probe. Extra fields are internal/fixture only;
    # absence of an HTTP execution flag never implies permission.
    verdict = evaluate(x)
    return {key: verdict[key] for key in ("state", "decision", "reason")}


@app.get("/metrics")
def metrics():
    return "aiops_policy_up 1\n"
