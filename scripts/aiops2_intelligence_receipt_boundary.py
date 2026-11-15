"""Pure, fail-closed sandbox receipt boundary; no external adapters or model calls."""
from __future__ import annotations

from datetime import datetime, timezone
import re

_SHA = re.compile(r"^[0-9a-f]{64}$")
_INJECTION = re.compile(r"ignore (?:all )?(?:previous|prior) instructions|system prompt|override (?:policy|hitl)|approve live", re.I)


def _time(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def qualify_sandbox_receipt(receipt: dict, *, now: str, max_age_seconds: int = 3600) -> dict:
    """Validate citations against supplied allowlisted receipts, never authorize effects.

    The allowlist is caller-supplied: this is NOT an authoritative tenant ACL.
    """
    result = {"schema": "aiops2.intelligence-boundary.v1", "mode": "SIMULATION_ONLY",
              "decision": "DENY", "hitl": "DENY", "effects_allowed": False,
              "live": "NO_GO", "qualified": False, "reasons": []}
    errors = result["reasons"]
    if not isinstance(receipt, dict):
        errors.append("INVALID_RECEIPT")
        return result
    if receipt.get("mode") != "SIMULATION_ONLY":
        errors.append("MODE_NOT_ISOLATED")
    tenant = receipt.get("tenant_id")
    if not isinstance(tenant, str) or not tenant:
        errors.append("TENANT_UNKNOWN")
    if receipt.get("incident_id") is None or receipt.get("service_path") != ["SAN", "Payments"]:
        errors.append("PATH_UNKNOWN")
    if receipt.get("critic_execution_id") in (None, receipt.get("analyst_execution_id")):
        errors.append("CRITIC_INDEPENDENCE_UNATTESTED")
    if receipt.get("critic_verdict") != "DENY":
        errors.append("CRITIC_NOT_DENY")
    if receipt.get("itil_operation") != "READ_ONLY":
        errors.append("ITIL_EFFECT_UNSAFE")
    if receipt.get("policy_decision") != "DENY" or receipt.get("hitl_decision") != "DENY":
        errors.append("POLICY_HITL_UNSAFE")
    try:
        reference = _time(now)
    except (TypeError, ValueError):
        errors.append("CLOCK_UNKNOWN")
        return result
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("EVIDENCE_MISSING")
        evidence = []
    allowed = set()
    for item in evidence:
        if not isinstance(item, dict):
            errors.append("EVIDENCE_MALFORMED")
            continue
        digest = item.get("sha256")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            errors.append("EVIDENCE_HASH_INVALID")
            continue
        if item.get("tenant_id") != tenant:
            errors.append("CROSS_TENANT_EVIDENCE")
            continue
        try:
            age = (reference - _time(item.get("observed_at"))).total_seconds()
            if age < 0 or age > max_age_seconds:
                errors.append("EVIDENCE_STALE_OR_FUTURE")
                continue
        except (ValueError, TypeError, OverflowError):
            errors.append("EVIDENCE_TIME_INVALID")
            continue
        allowed.add(digest)
        if _INJECTION.search(str(item.get("text", ""))):
            errors.append("PROMPT_INJECTION")
    citations = receipt.get("citations")
    if not isinstance(citations, list) or not citations or any(c not in allowed for c in citations):
        errors.append("CITATION_UNVERIFIED")
    if receipt.get("contradictions") is None or receipt.get("missing_evidence") is None:
        errors.append("CRITIC_COVERAGE_UNKNOWN")
    if receipt.get("runbook_ref") is None:
        errors.append("RUNBOOK_UNKNOWN")
    # A valid synthetic receipt is never a permission to execute.
    result["qualified"] = not errors
    return result
