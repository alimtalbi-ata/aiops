"""Offline, deterministic trust-boundary benchmark; no service calls or effects.

This checks a receipt contract, NOT real RAG grounding, ACL authorization,
cryptographic provenance or Critic process independence.
"""
from datetime import datetime, timezone, timedelta
import re

INJECTION = re.compile(r"ignore (all |previous )?instructions|system prompt|developer message|approve live|bypass (policy|hitl)", re.I)
REQUIRED = {"incident_id", "tenant", "mode", "dependency_path", "hypotheses",
            "citations", "contradictions", "missing_evidence", "critic",
            "policy", "hitl", "itil"}

def validate(receipt, now=None):
    """Return immutable-denial receipt and explicit rejection reasons."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    if not isinstance(receipt, dict):
        receipt = {}
    for field in sorted(REQUIRED - receipt.keys()):
        reasons.append("MISSING_" + field.upper())
    if receipt.get("mode") != "SIMULATION_ONLY":
        reasons.append("MODE_NOT_SIMULATION")
    if receipt.get("dependency_path") != ["SAN", "Payments"]:
        reasons.append("DEPENDENCY_PATH")
    tenant = receipt.get("tenant")
    if not isinstance(tenant, str) or not tenant:
        reasons.append("TENANT_UNKNOWN")
    hypotheses = receipt.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        reasons.append("HYPOTHESES_MISSING")
    else:
        for h in hypotheses:
            if not isinstance(h, dict) or not h.get("statement") or not h.get("citation_ids"):
                reasons.append("UNGROUNDED_HYPOTHESIS")
    citations = receipt.get("citations")
    ids = set()
    if not isinstance(citations, list) or not citations:
        reasons.append("CITATIONS_MISSING")
        citations = []
    for c in citations:
        if not isinstance(c, dict):
            reasons.append("CITATION_MALFORMED")
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not cid or cid in ids:
            reasons.append("CITATION_ID_INVALID")
        else:
            ids.add(cid)
        if c.get("tenant") != tenant or c.get("acl_verified") is not True:
            reasons.append("ACL_UNATTESTED")
        if c.get("source_type") not in ("evidence", "runbook"):
            reasons.append("SOURCE_UNATTESTED")
        try:
            ts = datetime.fromisoformat(c["observed_at"].replace("Z", "+00:00"))
            if ts.tzinfo is None or ts > now or now - ts > timedelta(hours=24):
                reasons.append("STALE_OR_FUTURE")
        except (KeyError, TypeError, ValueError, AttributeError):
            reasons.append("TIMESTAMP_INVALID")
        if not isinstance(c.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", c["sha256"]):
            reasons.append("DIGEST_INVALID")
        if INJECTION.search(str(c.get("excerpt", ""))):
            reasons.append("PROMPT_INJECTION")
    if isinstance(hypotheses, list):
        for h in hypotheses:
            if isinstance(h, dict):
                if any(cid not in ids for cid in h.get("citation_ids", []) if isinstance(h.get("citation_ids"), list)):
                    reasons.append("FABRICATED_CITATION")
    if not isinstance(receipt.get("contradictions"), list) or not isinstance(receipt.get("missing_evidence"), list):
        reasons.append("UNCERTAINTY_FIELDS_INVALID")
    critic = receipt.get("critic")
    if not isinstance(critic, dict) or critic.get("verdict") != "DENY" or critic.get("independence_attested") is not True or critic.get("execution_id") == receipt.get("analyst_execution_id"):
        reasons.append("CRITIC_NOT_ATTESTED")
    if receipt.get("policy") != "DENY" or receipt.get("hitl") != "DENY":
        reasons.append("FAIL_CLOSED_VIOLATION")
    if receipt.get("itil") != "READ_ONLY" or receipt.get("effects_allowed") is not False:
        reasons.append("EFFECT_BOUNDARY")
    return {"status": "CONTRACT_VALID_SYNTHETIC" if not reasons else "UNKNOWN",
            "reasons": sorted(set(reasons)), "policy": "DENY", "hitl": "DENY",
            "effects_allowed": False, "live": "NO_GO",
            "llm_executed": False, "glpi_executed": False, "temporal_executed": False}
