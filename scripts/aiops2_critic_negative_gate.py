"""Offline negative gate for synthetic Analyst/Critic receipts; never authorizes effects."""
from datetime import datetime, timezone
import re

SHA256 = re.compile(r"^[0-9a-f]{64}$")
INJECTION = re.compile(r"(?i)(ignore (all |previous )?instructions|system prompt|developer message|override policy|bypass (hitl|acl)|execute live)")

def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None

def assess(analysis: object, evidence: object, *, tenant: str, now: str, max_age_seconds: int = 300) -> dict:
    """Fail closed on untrusted model output, evidence and clock; no external calls."""
    failures = set()
    clock = _time(now)
    if clock is None or not isinstance(max_age_seconds, int) or max_age_seconds < 0:
        failures.add("INVALID_CLOCK")
    if not isinstance(analysis, dict) or not isinstance(evidence, list):
        failures.add("INVALID_SCHEMA")
        analysis, evidence = {}, []
    if analysis.get("tenant_id") != tenant or not isinstance(tenant, str) or not tenant:
        failures.add("TENANT_MISMATCH")
    hypotheses = analysis.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        failures.add("MISSING_HYPOTHESIS")
        hypotheses = []
    indexed = {}
    for item in evidence:
        if not isinstance(item, dict):
            failures.add("INVALID_EVIDENCE")
            continue
        ref, digest = item.get("id"), item.get("sha256")
        if not isinstance(ref, str) or not ref or ref in indexed or not isinstance(digest, str) or not SHA256.fullmatch(digest):
            failures.add("INVALID_EVIDENCE")
            continue
        indexed[ref] = item
        if item.get("tenant_id") != tenant:
            failures.add("TENANT_MISMATCH")
        observed = _time(item.get("observed_at"))
        if clock is None or observed is None or not 0 <= (clock-observed).total_seconds() <= max_age_seconds:
            failures.add("STALE_OR_FUTURE_EVIDENCE")
        if INJECTION.search(str(item.get("text", ""))):
            failures.add("PROMPT_INJECTION")
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict) or not isinstance(hypothesis.get("claim"), str):
            failures.add("INVALID_HYPOTHESIS")
            continue
        if INJECTION.search(hypothesis["claim"]):
            failures.add("PROMPT_INJECTION")
        refs = hypothesis.get("citations")
        if not isinstance(refs, list) or not refs:
            failures.add("MISSING_CITATIONS")
            continue
        if any(not isinstance(ref, str) or ref not in indexed for ref in refs):
            failures.add("UNSUPPORTED_CITATION")
        if hypothesis.get("contradictions") is None or not isinstance(hypothesis["contradictions"], list):
            failures.add("CONTRADICTIONS_UNASSESSED")
        elif hypothesis["contradictions"]:
            failures.add("CONTRADICTION_REQUIRES_REVIEW")
    critic = analysis.get("critic")
    if not isinstance(critic, dict) or critic.get("independent") is not True or critic.get("disposition") not in ("REJECT", "NEEDS_MORE_EVIDENCE", "SUPPORTED_SYNTHETIC_HYPOTHESIS"):
        failures.add("CRITIC_UNVERIFIED")
    return {"schema": "aiops2.synthetic-critic-negative-gate.v1",
            "status": "BLOCKED" if failures else "PASS_SYNTHETIC_ONLY",
            "reasons": sorted(failures), "policy": "DENY_LIVE",
            "hitl": "DENY", "effects_allowed": False,
            "llm_executed": False, "glpi_executed": False, "temporal_executed": False}
