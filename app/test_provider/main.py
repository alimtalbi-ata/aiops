"""Deterministic, synthetic-only OpenAI-compatible provider for CI integration tests."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def build_output(system, payload):
    evidence = payload.get("evidence", [])
    known = [item.get("evidence_id") for item in evidence if isinstance(item.get("evidence_id"), str)]
    analyst = payload.get("analyst")
    if analyst is not None or "independent AIOps Critic" in system:
        refs = []
        if isinstance(analyst, dict):
            for hypothesis in analyst.get("hypotheses", []):
                refs.extend(hypothesis.get("supporting_evidence_ids", []))
        supported = bool(refs) and set(refs).issubset(set(known))
        issues = [] if supported else [{
            "code": "UNSUPPORTED_CLAIM",
            "description": "CI critic could not verify the analyst evidence references.",
            "evidence_ids": [item for item in refs if item not in known],
        }]
        return {
            "contract_version": "2.0",
            "validated": supported,
            "issues": issues,
            "claim_checks": [{
                "claim": "The primary hypothesis is grounded in the supplied CI evidence.",
                "supported": supported,
                "supporting_evidence_ids": refs[:3] if supported else [],
                "contradicting_evidence_ids": [],
            }],
            "additional_evidence_needed": [] if supported else ["valid evidence identifiers"],
            "unsafe_actions": [],
            "diagnostic_confidence": 0.95 if supported else 0.0,
            "final_recommendation": ("ESCALATE" if analyst and analyst.get("severity") == "P1" else "OBSERVE") if supported else "HUMAN_APPROVAL",
            "limitations": ["Deterministic synthetic CI provider; not a real model evaluation."],
        }

    incident = payload.get("incident", {})
    claims = " ".join(str(item.get("claim", "")) for item in evidence).lower()
    title = str(incident.get("title", "")).lower()
    if ("91 percent" in claims or "91%" in claims or ("capacity" in title and "pool" in title)):
        severity = "P2"
        rationale = "The supplied synthetic evidence reports capacity pressure without current service impact."
        confidence = 0.91
    elif any(term in claims + " " + title for term in ("184 fc errors", "one active path", "critical", "payment", "multipath", "fabric")):
        severity = "P1"
        rationale = "The supplied synthetic evidence reports critical path/fabric degradation with service impact."
        confidence = 0.96
    else:
        severity = "UNKNOWN"
        rationale = "The synthetic evidence is insufficient to establish a severity."
        confidence = 0.25
    refs = known[:5]
    return {
        "contract_version": "2.0",
        "classification": "storage-path-degradation" if severity == "P1" else ("storage-capacity-pressure" if severity == "P2" else "unknown"),
        "severity": severity,
        "severity_rationale": rationale,
        "hypotheses": [{
            "id": "H-CI-1",
            "statement": rationale,
            "confidence": confidence,
            "supporting_evidence_ids": refs,
            "contradicting_evidence_ids": [],
            "assumptions": [] if refs else ["insufficient evidence in this synthetic CI scenario"],
        }],
        "alternatives": [],
        "recommended_actions": [],
        "missing_information": [] if refs else ["fresh source evidence"],
        "unknowns": [] if not refs else [],
        "contradictions": [],
        "confidence": confidence,
        "confidence_basis": "Deterministic synthetic CI fixture; confidence is not a real-model calibration measurement.",
        "limitations": ["CI-only fake provider", "synthetic evidence only"],
    }

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def send_json(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/health", "/ready"):
            self.send_json(200, {"status": "ok", "component": "deterministic-test-provider", "synthetic_only": True})
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self.send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            messages = request.get("messages", [])
            system = str(messages[0].get("content", "")) if messages else ""
            payload = json.loads(messages[-1].get("content", "{}")) if messages else {}
            output = build_output(system, payload)
            self.send_json(200, {"id": "chatcmpl-ci-fixture", "object": "chat.completion", "model": request.get("model", "ci-deterministic"), "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(output, ensure_ascii=False)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        except Exception as exc:
            self.send_json(500, {"error": "fixture_provider_error", "type": type(exc).__name__})

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 818), Handler).serve_forever()
