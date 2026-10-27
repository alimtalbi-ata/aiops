"""Read-only NOC Copilot. No free-form LLM execution or ungrounded answers."""
import os
import secrets
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from shared.http import INTERNAL_TOKEN, get_json
from copilot.grounding import (
    RUN_ID, classify, evidence_answer, now_utc, snapshot_answer, unknown,
)

app = FastAPI(title="ACME AioOps Copilot", version="2.1.0")
CORE = os.getenv("CORE_URL", "http://aiops2-core:810")
TWIN = os.getenv("TWIN_URL", "http://aiops2-twin:811")
EVID = os.getenv("EVIDENCE_URL", "http://aiops2-evidence:812")


class Q(BaseModel):
    question: str = Field(min_length=1, max_length=512)
    run_id: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "component": "copilot",
        "mode": "read-only-scoped-grounding",
        "unsupported_claim_policy": "UNKNOWN",
        "rbac": "operator gateway only; per-user ACL not qualified",
    }


def require_internal(authorization):
    scheme, separator, credential = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator or not credential
            or not secrets.compare_digest(credential, INTERNAL_TOKEN)):
        raise HTTPException(status_code=401, detail="trusted gateway required")


@app.post("/api/copilot/query")
def query(x: Q, authorization: str | None = Header(default=None)):
    # The public Portal must authenticate its operator before forwarding.
    # This internal token is service authentication, NOT per-user/tenant RBAC.
    require_internal(authorization)
    intent = classify(x.question)
    if intent is None:
        return unknown("UNSUPPORTED_QUESTION")
    if intent == "run_evidence":
        if not x.run_id or not RUN_ID.fullmatch(x.run_id):
            return unknown("VALID_RUN_ID_REQUIRED")
    elif x.run_id:
        # Never silently answer an unscoped global query when a run was requested.
        return unknown("QUESTION_SCOPE_MISMATCH")

    timestamp = now_utc()
    try:
        if intent in ("runs_total", "open_incidents"):
            return snapshot_answer(intent, get_json(CORE, "/api/dashboard"), timestamp)
        if intent == "topology":
            return snapshot_answer(intent, get_json(TWIN, "/api/twin/summary"), timestamp)
        if intent == "run_evidence":
            safe_id = quote(x.run_id, safe="")
            run = get_json(CORE, f"/api/runs/{safe_id}")
            if (not isinstance(run, dict) or
                    not isinstance(run.get("run"), dict) or
                    run["run"].get("run_id") != x.run_id or
                    run["run"].get("mode") not in ("DEMO", "REPLAY", "STORY")):
                return unknown("RUN_NOT_AUTHORIZED_FOR_SYNTHETIC_READ")
            evidence = get_json(EVID, f"/api/evidence?run_id={safe_id}&limit=100")
            return evidence_answer(x.run_id, run, evidence, timestamp)
    except Exception:
        # Upstream errors must not expose internal URLs, tokens or raw response bodies.
        return unknown("SOURCE_UNAVAILABLE")
    return unknown("UNSUPPORTED_QUESTION")
