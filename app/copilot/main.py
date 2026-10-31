import hashlib
import json
import os
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from shared.http import get_json, post_json

app = FastAPI(title="ACME AioOps Copilot", version="3.0.0")
CORE = os.getenv("CORE_URL", "http://aiops2-core:810")
EVID = os.getenv("EVIDENCE_URL", "http://aiops2-evidence:812")
INTELLIGENCE = os.getenv("INTELLIGENCE_URL", "http://aiops2-intelligence:817")
RUN_RE = re.compile(r"RUN-[A-Za-z0-9_-]{6,120}")


class Q(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    run_id: str = Field(min_length=10, max_length=128)
    ticket_context: dict = Field(default_factory=dict)


def obj(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


@app.get("/health")
def health():
    return {"status": "ok", "component": "copilot", "mode": "run-scoped-nim-assistant",
            "unsupported_claim_policy": "UNKNOWN", "execution_allowed": False}


@app.post("/api/copilot/query")
def query(x: Q):
    if not RUN_RE.fullmatch(x.run_id):
        raise HTTPException(422, "invalid_run_id")
    try:
        detail = get_json(CORE, "/api/runs/" + x.run_id)
        ledger = get_json(CORE, "/api/runs/" + x.run_id + "/ai-ledger")
        ev = get_json(EVID, "/api/evidence?run_id=" + x.run_id + "&limit=100")
        incidents = get_json(CORE, "/api/incidents?limit=500")
    except Exception:
        raise HTTPException(503, "run_scoped_context_unavailable")
    run = detail.get("run") if isinstance(detail, dict) else None
    if not isinstance(run, dict) or run.get("run_id") != x.run_id:
        raise HTTPException(404, "run_not_found")
    if run.get("mode") not in ("DEMO", "REPLAY", "STORY") or run.get("scenario_id") != "SCN-GOLDEN-PAYMENT-P1":
        raise HTTPException(403, "assistant_demo_scope_required")
    if run.get("status") != "RESOLVED":
        raise HTTPException(409, "assistant_requires_resolved_demo_run")
    incident_items = incidents.get("items", []) if isinstance(incidents, dict) else []
    incident = next((i for i in incident_items if isinstance(i, dict) and i.get("incident_id") == run.get("incident_id")), None)
    evidence = ev.get("items") if isinstance(ev, dict) else None
    if not incident or not isinstance(evidence, list) or not evidence:
        raise HTTPException(409, "run_incident_or_evidence_unavailable")
    analyses = ledger.get("analyses", []) if isinstance(ledger, dict) else []
    critiques = ledger.get("critiques", []) if isinstance(ledger, dict) else []
    analyst = obj(analyses[-1].get("output")) if analyses and isinstance(analyses[-1], dict) else {}
    critic = obj(critiques[-1].get("output")) if critiques and isinstance(critiques[-1], dict) else {}
    if not analyst or not critic:
        raise HTTPException(409, "validated_analyst_critic_context_required")
    ticket = x.ticket_context if isinstance(x.ticket_context, dict) else {}
    context = {
        "run_id": x.run_id, "scenario_id": run.get("scenario_id"), "run_status": run.get("status"),
        "analyst": analyst, "critic": critic,
        "glpi_ticket": {"id": str(ticket.get("id", ""))[:32],
                        "title": str(ticket.get("title", ""))[:500],
                        "description": str(ticket.get("description", ""))[:6000],
                        "provenance": "untrusted GLPI ticket text"},
    }
    try:
        answer = post_json(INTELLIGENCE, "/api/intelligence/answer", {
            "incident": incident, "evidence": evidence, "mode": run["mode"],
            "context": context, "question": x.question,
        }, timeout=150)
    except Exception:
        raise HTTPException(502, "nim_assistant_answer_unavailable")
    body = answer.get("answer") if isinstance(answer, dict) else None
    if not isinstance(body, dict):
        raise HTTPException(502, "assistant_contract_invalid")
    known = {i.get("evidence_id") for i in evidence if isinstance(i, dict)}
    refs = sorted({r for claim in body.get("claims", []) if isinstance(claim, dict)
                   for r in claim.get("supporting_evidence_ids", []) + claim.get("contradicting_evidence_ids", [])
                   if isinstance(r, str)})
    if not set(refs).issubset(known):
        raise HTTPException(502, "assistant_evidence_scope_mismatch")
    usage = answer.get("model_invocation", {}) if isinstance(answer.get("model_invocation"), dict) else {}
    question_hash = hashlib.sha256(x.question.encode("utf-8")).hexdigest()
    event = {
        "expected_version": int(run.get("version", 0)), "stage": "LEARN",
        "event_type": "COPILOT_ANSWER_RECORDED", "status": "RECORDED",
        "event_key": "COPILOT:" + hashlib.sha256((x.run_id + ":" + question_hash).encode()).hexdigest(),
        "evidence_ids": refs, "decision": "NO_EXECUTION",
        "payload": {"answer": body, "provider": answer.get("provider"), "model": answer.get("model"),
                    "prompt_version": answer.get("prompt_version"), "model_invocation": usage,
                    "question_sha256": question_hash, "glpi_ticket_id": str(ticket.get("id", ""))[:32] or None,
                    "actor_type": "DEMO_OPERATOR", "execution_allowed": False},
    }
    try:
        receipt = post_json(CORE, "/api/runs/" + x.run_id + "/events", event, timeout=15)
    except Exception:
        raise HTTPException(503, "assistant_audit_persistence_failed")
    if not isinstance(receipt, dict) or not receipt.get("sequence"):
        raise HTTPException(502, "assistant_audit_receipt_invalid")
    return {"answer": body, "run_id": x.run_id, "event_sequence": receipt["sequence"],
            "sources": ["core:/api/runs/" + x.run_id, "core:/api/runs/" + x.run_id + "/ai-ledger",
                        "evidence:/api/evidence?run_id=" + x.run_id]
                       + (["glpi:/Ticket/" + str(ticket.get("id"))] if ticket.get("id") else []),
            "provider": answer.get("provider"), "model": answer.get("model"),
            "prompt_version": answer.get("prompt_version"), "model_invocation": usage,
            "evidence_count": len(evidence), "execution_allowed": False, "approval_recorded": False}
