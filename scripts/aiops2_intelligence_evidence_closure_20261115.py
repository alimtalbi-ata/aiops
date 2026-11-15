"""Offline, untrusted Analyst/Critic receipt evaluator. No external I/O or effects."""
from datetime import datetime, timezone, timedelta

MAX_AGE = timedelta(hours=24)
INJECTION_MARKERS = ("ignore previous instructions", "system prompt", "override policy", "approve live", "disable hitl")

def evaluate(receipt, trusted_evidence, now):
    """Return fail-closed verdict. trusted_evidence must come from an authoritative caller.

    This is a synthetic contract checker, NOT authentication, a cryptographic
    signature verifier, an independent Critic executor or a policy engine.
    """
    errors = []
    if not isinstance(receipt, dict) or not isinstance(trusted_evidence, dict):
        return {"status": "UNKNOWN", "errors": ["INVALID_INPUT"], "policy": "DENY",
                "hitl": "DENY", "effects_allowed": False, "live": "NO_GO"}
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if receipt.get("mode") != "SIMULATION_ONLY":
        errors.append("MODE")
    if receipt.get("tenant") in (None, ""):
        errors.append("TENANT_UNKNOWN")
    if receipt.get("dependency_path") != ["SAN", "Payments"]:
        errors.append("DEPENDENCY_PATH")
    if not receipt.get("incident_id") or not receipt.get("runbook_id"):
        errors.append("CONTEXT_MISSING")
    analyst = receipt.get("analyst") or {}
    critic = receipt.get("critic") or {}
    if not isinstance(analyst, dict) or not isinstance(critic, dict):
        errors.append("ANALYSIS_SCHEMA")
        analyst, critic = {}, {}
    if not analyst.get("hypotheses") or not isinstance(analyst.get("contradictions"), list) or not isinstance(analyst.get("missing_evidence"), list):
        errors.append("ANALYST_INCOMPLETE")
    if not critic.get("challenges") or critic.get("run_id") in (None, analyst.get("run_id")):
        errors.append("CRITIC_UNATTESTED")
    citations = analyst.get("citations")
    if not isinstance(citations, list) or not citations:
        errors.append("CITATIONS_MISSING")
        citations = []
    for citation in citations:
        evidence = trusted_evidence.get(citation) if isinstance(citation, str) else None
        if not isinstance(evidence, dict):
            errors.append("CITATION_UNKNOWN")
            continue
        if evidence.get("tenant") != receipt.get("tenant") or evidence.get("acl_allowed") is not True:
            errors.append("ACL_DENIED")
        try:
            observed = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
            if observed.tzinfo is None or observed > now or now - observed > MAX_AGE:
                errors.append("EVIDENCE_STALE")
        except (KeyError, ValueError, AttributeError, TypeError):
            errors.append("EVIDENCE_TIME_UNKNOWN")
        if any(marker in str(evidence.get("text", "")).lower() for marker in INJECTION_MARKERS):
            errors.append("UNTRUSTED_INSTRUCTION")
    if receipt.get("policy") != "DENY" or receipt.get("hitl") != "DENY" or receipt.get("effects_allowed") is not False:
        errors.append("EFFECT_BOUNDARY")
    if receipt.get("itil") != "READ_ONLY":
        errors.append("ITIL_WRITE")
    return {"status": "CONTRACT_OK_SYNTHETIC" if not errors else "UNKNOWN",
            "errors": sorted(set(errors)), "policy": "DENY", "hitl": "DENY",
            "effects_allowed": False, "live": "NO_GO"}
