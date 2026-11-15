"""Offline SAN->Payments Analyst/Critic trust-boundary receipt validator.

No LLM, GLPI, Temporal, database, network or external effects.
All inputs are untrusted; success only means the synthetic contract is coherent.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

REQUIRED = {"incident_id", "tenant_id", "mode", "service_path", "evidence",
            "hypotheses", "critic", "policy", "itil"}
MAX_AGE_SECONDS = 3600
INJECTION_MARKERS = ("ignore previous instructions", "system prompt",
                     "override policy", "disable hitl", "approve live",
                     "exfiltrate", "developer message")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def validate(receipt: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Return fail-closed decision and stable reason codes; never authorize effects."""
    reasons: set[str] = set()
    if not isinstance(receipt, dict) or not REQUIRED.issubset(receipt):
        return {"status": "UNKNOWN", "reasons": ["SCHEMA"], "effects_allowed": False,
                "live": "NO_GO"}
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    tenant = receipt["tenant_id"]
    if not isinstance(tenant, str) or not tenant.strip():
        reasons.add("TENANT_UNKNOWN")
    if receipt["mode"] != "SIMULATION_ONLY":
        reasons.add("MODE_NOT_SIMULATION")
    if receipt["service_path"] != ["SAN", "Payments"]:
        reasons.add("DEPENDENCY_PATH")
    evidence = receipt["evidence"]
    if not isinstance(evidence, list) or not evidence:
        reasons.add("EVIDENCE_MISSING")
        evidence = []
    refs = set()
    for item in evidence:
        if not isinstance(item, dict):
            reasons.add("EVIDENCE_SCHEMA")
            continue
        ref = item.get("id")
        if not isinstance(ref, str) or not ref or ref in refs:
            reasons.add("EVIDENCE_ID")
        else:
            refs.add(ref)
        if item.get("tenant_id") != tenant or item.get("acl_verified") is not True:
            reasons.add("ACL_UNVERIFIED")
        stamp = _utc(item.get("observed_at"))
        if stamp is None or not 0 <= (now - stamp).total_seconds() <= MAX_AGE_SECONDS:
            reasons.add("EVIDENCE_STALE")
        content = item.get("content", "")
        if not isinstance(content, str) or any(x in content.lower() for x in INJECTION_MARKERS):
            reasons.add("UNTRUSTED_INSTRUCTION")
    hypotheses = receipt["hypotheses"]
    if not isinstance(hypotheses, list) or not hypotheses:
        reasons.add("HYPOTHESIS_MISSING")
        hypotheses = []
    for h in hypotheses:
        if not isinstance(h, dict):
            reasons.add("HYPOTHESIS_SCHEMA")
            continue
        citations = h.get("citations")
        if not isinstance(citations, list) or not citations or any(
            not isinstance(c, str) or c not in refs for c in citations
        ):
            reasons.add("CITATION_UNVERIFIED")
        if not isinstance(h.get("contradictions"), list) or not isinstance(
            h.get("missing_evidence"), list
        ):
            reasons.add("ANALYSIS_INCOMPLETE")
    critic = receipt["critic"]
    if not isinstance(critic, dict) or critic.get("independence_attested") is not True or (
        not isinstance(critic.get("analyst_run_id"), str)
        or not isinstance(critic.get("critic_run_id"), str)
        or critic.get("analyst_run_id") == critic.get("critic_run_id")
    ):
        reasons.add("CRITIC_INDEPENDENCE_UNKNOWN")
    # This only validates a claimed attestation, not its trusted provenance.
    policy = receipt["policy"]
    if not isinstance(policy, dict) or policy.get("decision") != "DENY" or policy.get("hitl") != "DENY":
        reasons.add("POLICY_NOT_DENY")
    itil = receipt["itil"]
    if not isinstance(itil, dict) or itil.get("read_only") is not True or itil.get("writes") != 0:
        reasons.add("ITIL_EFFECT_RISK")
    return {"status": "CONTRACT_VALID_SYNTHETIC" if not reasons else "UNKNOWN",
            "reasons": sorted(reasons), "effects_allowed": False, "live": "NO_GO"}
