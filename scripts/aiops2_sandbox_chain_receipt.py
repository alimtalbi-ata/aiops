"""Offline synthetic chain receipt; never calls a runtime adapter."""
from datetime import datetime

STAGES = ("SAN", "Payments", "Analyst", "Critic", "Policy/HITL", "ITIL")

def receipt(case):
    failures = []
    if not isinstance(case, dict):
        case = {}
        failures.append("INVALID_INPUT")
    if case.get("mode") != "SIMULATION_ONLY":
        failures.append("MODE_NOT_SIMULATION")
    if case.get("tenant") != "acme-demo" or case.get("actor_tenant") != case.get("tenant"):
        failures.append("TENANT_ACL_UNATTESTED")
    if case.get("path") != ["SAN", "Payments"]:
        failures.append("DEPENDENCY_UNATTESTED")
    evidence = case.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        failures.append("EVIDENCE_MISSING")
        evidence = []
    ids = set()
    for ev in evidence:
        if not isinstance(ev, dict) or not isinstance(ev.get("id"), str) or not ev.get("id"):
            failures.append("INVALID_EVIDENCE")
            continue
        if ev["id"] in ids:
            failures.append("DUPLICATE_EVIDENCE")
        ids.add(ev["id"])
        if ev.get("tenant") != case.get("tenant"):
            failures.append("CROSS_TENANT_EVIDENCE")
        try:
            timestamp = datetime.fromisoformat(ev["observed_at"].replace("Z", "+00:00"))
            now = datetime.fromisoformat(case["as_of"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None or now.tzinfo is None or not 0 <= (now - timestamp).total_seconds() <= 300:
                failures.append("STALE_OR_FUTURE_EVIDENCE")
        except (ValueError, TypeError, KeyError, AttributeError):
            failures.append("INVALID_TIMESTAMP")
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    citations = analysis.get("citations")
    if not isinstance(citations, list) or not citations or any(not isinstance(c, str) or c not in ids for c in citations):
        failures.append("UNSUPPORTED_CITATION")
    if not isinstance(analysis.get("hypotheses"), list) or not analysis["hypotheses"]:
        failures.append("HYPOTHESES_MISSING")
    if not isinstance(analysis.get("contradictions"), list) or not isinstance(analysis.get("missing_evidence"), list):
        failures.append("UNCERTAINTY_NOT_RECORDED")
    failures.append("CRITIC_INDEPENDENCE_UNATTESTED")
    if case.get("hitl") != "DENY":
        failures.append("HITL_NOT_DENY")
    return {"schema": "aiops2.synthetic-chain-receipt.v1", "stages": list(STAGES),
            "mode": "SIMULATION_ONLY", "qualification": "SYNTHETIC_ONLY",
            "analysis_state": "UNKNOWN" if failures else "SUPPORTED_SYNTHETIC",
            "failures": sorted(set(failures)), "policy": "DENY_LIVE",
            "hitl": "DENY", "itil": "READ_ONLY_NOT_EXECUTED",
            "effects_allowed": False, "live": "NO_GO",
            "llm": "NOT_EXECUTED", "glpi": "NOT_EXECUTED", "temporal": "NOT_EXECUTED"}

if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(receipt(json.load(sys.stdin)), sort_keys=True))
