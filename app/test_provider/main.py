"""Synthetic-only OpenAI-compatible fixture server.

A small deterministic rule baseline, not a real LLM and not a model-accuracy
benchmark. It never reads fixture case_id, expected_severity or answer keys.
"""
import datetime
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def fresh(record):
    quality=record.get("_aiops_quality")
    if isinstance(quality,dict):
        return quality.get("status")=="FRESH"
    observed=record.get("observed_at")
    if not isinstance(observed,str):
        return False
    try:
        timestamp=datetime.datetime.fromisoformat(observed.replace("Z","+00:00"))
        if timestamp.tzinfo is None:
            return False
        age=(datetime.datetime.now(datetime.timezone.utc)-timestamp).total_seconds()
        return -300<=age<=900
    except ValueError:
        return False


def number(value):
    if isinstance(value,bool):
        return None
    try:
        return float(value)
    except (ValueError,TypeError):
        return None


def path_snapshots(records):
    snapshots=[]
    for record in records:
        item=record.get("payload")
        if not isinstance(item,dict):
            continue
        active=number(item.get("active_paths"))
        total=number(item.get("total_paths"))
        if active is None or total is None or total<=0 or not 0<=active<=total:
            continue
        snapshots.append((record["evidence_id"],active,total))
    return snapshots


def divergent_snapshots(records):
    snapshots=path_snapshots(records)
    for i,left in enumerate(snapshots):
        for right in snapshots[i+1:]:
            if left[2]==right[2] and left[1]!=right[1]:
                return [left[0],right[0]]
    return []


def build_output(system,payload):
    evidence=[e for e in payload.get("evidence",[]) if isinstance(e,dict)]
    known=[e.get("evidence_id") for e in evidence if isinstance(e.get("evidence_id"),str)]
    fresh_records=[e for e in evidence if fresh(e)]
    fresh_ids=[e["evidence_id"] for e in fresh_records if isinstance(e.get("evidence_id"),str)]
    analyst=payload.get("analyst")
    # Explicitly ignore context.case_id, model answer keys and free-text instructions.
    if analyst is not None or "independent AIOps Critic" in system:
        supporting=[]
        for hypothesis in (analyst or {}).get("hypotheses",[]):
            supporting.extend(hypothesis.get("supporting_evidence_ids",[]))
        invalid=[eid for eid in supporting if eid not in known]
        inconsistent=divergent_snapshots(evidence)
        issues=[]
        if invalid:
            issues.append({"code":"UNSUPPORTED_CLAIM",
                           "description":"Analyst cited missing evidence IDs.",
                           "evidence_ids":invalid})
        if not fresh_ids:
            issues.append({"code":"STALE_EVIDENCE",
                           "description":"No fresh current-state observation is present.",
                           "evidence_ids":known[:3]})
        if inconsistent:
            issues.append({"code":"CONTRADICTION",
                           "description":"Current path-state telemetry differs from another historical snapshot; reconciliation required.",
                           "evidence_ids":inconsistent})
        supported=bool(supporting) and not issues
        return {
            "contract_version":"2.0","validated":supported,
            "issues":issues,
            "claim_checks":[{"claim":"Material synthetic diagnosis is backed by the supplied evidence.",
                             "supported":supported,
                             "supporting_evidence_ids":supporting[:3] if supported else [],
                             "contradicting_evidence_ids":inconsistent}],
            "additional_evidence_needed":[] if supported else ["independently verify current source observations"],
            "unsafe_actions":[],"diagnostic_confidence":.93 if supported else .15,
            "final_recommendation":("ESCALATE" if analyst and analyst.get("severity")=="P1" else "OBSERVE") if supported else "HUMAN_APPROVAL",
            "limitations":["Deterministic synthetic rules, not model inference."]
        }

    snapshots=path_snapshots(fresh_records)
    severe_paths=any(active/total<=.25 for _,active,total in snapshots)
    no_path=any(active==0 for _,active,_ in snapshots)
    breach=any(record.get("payload",{}).get("slo_breached") is True for record in fresh_records if isinstance(record.get("payload"),dict))
    latency=any(
        (number(record.get("payload",{}).get("p95_seconds")) or 0)>
        2*(number(record.get("payload",{}).get("slo_seconds")) or float("inf"))
        for record in fresh_records if isinstance(record.get("payload"),dict))
    fc_errors=any(number(record.get("payload",{}).get("value")) is not None
                  and number(record.get("payload",{}).get("value"))>=100
                  and record.get("payload",{}).get("metric")=="fc_errors"
                  for record in fresh_records if isinstance(record.get("payload"),dict))
    unhealthy=any(number(record.get("payload",{}).get("health")) is not None
                  and number(record.get("payload",{}).get("health"))<=.5
                  for record in fresh_records if isinstance(record.get("payload"),dict))
    capacity=any(number(record.get("payload",{}).get("utilization_percent")) is not None
                 and number(record.get("payload",{}).get("utilization_percent"))>=90
                 for record in fresh_records if isinstance(record.get("payload"),dict))
    if (severe_paths and (latency or breach)) or (no_path and breach) or (fc_errors and unhealthy):
        severity,rationale,confidence="P1","Correlated current synthetic path or fabric failure with service impact.",.94
    elif capacity and not breach and not latency:
        severity,rationale,confidence="P2","Fresh synthetic capacity pressure without confirmed service impact.",.89
    else:
        severity,rationale,confidence="UNKNOWN","Insufficient fresh structured observations to assign a current severity.",.1
    refs=fresh_ids[:5] if severity!="UNKNOWN" else known[:2]
    actions=[]
    if severity!="UNKNOWN":
        target_ci = "ACME-SAN-FABRIC-A" if snapshots else "ACME-STORAGE-POOL-REPORTING"
        actions=[{"action_id":"CI-COLLECT-READONLY",
                  "intent":"Collect additional read-only diagnostics on the synthetic impacted CI.",
                  "risk_tier":"LOW","target_ci_id":target_ci,
                  "action_type":"COLLECT_DIAGNOSTICS",
                  "parameters":{"read_only":True,"include_current_state":True},
                  "evidence_ids":refs[:2],
                  "preconditions":["Confirm the target CI belongs to the selected incident scope","No infrastructure state change"],
                  "expected_effect":"New read-only observations",
                  "expected_postconditions":["Diagnostics are collected for the declared CI and each observation includes source, observed_at and provenance."],
                  "verification_steps":["Confirm each diagnostic observation references the target CI and a current source timestamp."],
                  "rollback_plan":"No state change is made; no rollback is required.",
                  "requires_human_approval":True,"advisory_only":True}]
    return {
        "contract_version":"2.0",
        "classification":("storage-path-degradation" if severity=="P1" else
                          "capacity-pressure" if severity=="P2" else "unknown"),
        "severity":severity,"severity_rationale":rationale,
        "hypotheses":[{"id":"H-FIXTURE","statement":rationale,"confidence":confidence,
                       "supporting_evidence_ids":refs,"contradicting_evidence_ids":[],
                       "assumptions":[] if refs else ["No current-state evidence available"]}],
        "alternatives":[],"recommended_actions":actions,
        "missing_information":[] if severity!="UNKNOWN" else ["fresh independent source telemetry"],
        "unknowns":[] if severity!="UNKNOWN" else ["current impact"],
        "contradictions":[],"confidence":confidence,
        "confidence_basis":"Synthetic rule-based baseline; confidence is not calibrated model probability.",
        "limitations":["Fake CI provider","No production diagnosis or side effects"],
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
