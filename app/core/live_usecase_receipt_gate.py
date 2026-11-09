"""Read-only fail-closed validation of Debian live-usecase receipts.

A receipt is a claim, not authorization to execute. Never performs IO.
"""
from datetime import datetime, timezone
from enum import Enum
import math
import re


class Qualification(str, Enum):
    HOLD = "HOLD"
    UNVERIFIED = "UNVERIFIED"
    PASS_CLAIM_ONLY = "PASS_CLAIM_ONLY"


REQUIRED = frozenset({
    "core_run_consistency", "evidence_readback", "critic_policy_outbox",
    "policy_denial_safety", "temporal_worker_history", "hitl_action_binding",
    "itsm_cross_reference", "platform_smoke", "portal_runtime",
    "intelligence_runtime",
})


def classify(receipt, now=None, max_age_seconds=180):
    """Only accept fresh, complete read-only claims; never grant action admission."""
    if not isinstance(receipt, dict) or receipt.get("schema") != "aiops2-live-usecase-qualification-v1":
        return Qualification.UNVERIFIED
    if receipt.get("read_only") is not True:
        return Qualification.UNVERIFIED
    # Reject invalid freshness policy inputs: NaN comparisons otherwise bypass
    # both age bounds and can turn an expired receipt into a PASS claim.
    if (type(max_age_seconds) not in (int, float)
            or not math.isfinite(max_age_seconds) or max_age_seconds < 0):
        return Qualification.UNVERIFIED
    try:
        timestamp = datetime.fromisoformat(receipt["utc"].replace("Z", "+00:00"))
        clock = now if now is not None else datetime.now(timezone.utc)
        age = (clock - timestamp).total_seconds()
        if timestamp.tzinfo is None or clock.tzinfo is None or age < -60 or age > max_age_seconds:
            return Qualification.UNVERIFIED
    except (ValueError, TypeError, KeyError, AttributeError):
        return Qualification.UNVERIFIED
    # Every qualification is scoped to one canonical Run. A missing or malformed
    # identity cannot establish even a read-only PASS claim.
    run_id = receipt.get("run_id")
    if (type(run_id) is not str or re.fullmatch(r"RUN-[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id) is None):
        return Qualification.UNVERIFIED
    checks = receipt.get("checks")
    if not isinstance(checks, list) or len(checks) != len(REQUIRED):
        return Qualification.UNVERIFIED
    by_name = {}
    for item in checks:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            return Qualification.UNVERIFIED
        name = item["name"]
        if name in by_name or name not in REQUIRED or item.get("status") not in ("PASS", "HOLD", "NOT_APPLICABLE", "UNVERIFIED"):
            return Qualification.UNVERIFIED
        by_name[name] = item
    if set(by_name) != REQUIRED:
        return Qualification.UNVERIFIED
    # An explicit cross-run evidence reference contradicts the receipt identity.
    # Absence is not proof of matching; other gates still determine completeness.
    for item in by_name.values():
        evidence = item.get("evidence")
        if isinstance(evidence, dict) and "run_id" in evidence:
            if type(evidence["run_id"]) is not str or evidence["run_id"] != run_id:
                return Qualification.UNVERIFIED
    # A blocked run may legitimately lack HITL and Worker execution evidence.
    optional = {"temporal_worker_history", "hitl_action_binding"}
    for name, item in by_name.items():
        if item["status"] == "NOT_APPLICABLE":
            if name not in optional or by_name["policy_denial_safety"]["status"] != "PASS":
                return Qualification.UNVERIFIED
    # A policy-denial safety probe alone does not prove this run was blocked.
    # NOT_APPLICABLE for Worker/HITL requires the blocked-run evidence bound
    # to the same receipt, rather than an unrelated successful safety test.
    if any(by_name[name]["status"] == "NOT_APPLICABLE" for name in optional):
        denial = by_name["policy_denial_safety"].get("evidence")
        # An unrelated blocked run must never exempt this run from HITL/Temporal checks.
        run_id = receipt.get("run_id")
        if (not isinstance(run_id, str) or not run_id.strip()
                or not isinstance(denial, dict) or denial.get("run_id") != run_id
                or denial.get("run_status") != "BLOCKED"
                or denial.get("critic_policy_outbox") != "PASS"
                or by_name["critic_policy_outbox"]["status"] != "PASS"):
            return Qualification.UNVERIFIED
    execution = receipt.get("probe_execution")
    if not isinstance(execution, dict) or any(
        not isinstance(execution.get(name), dict) or type(execution[name].get("exit")) is not int
        or execution[name]["exit"] != 0 or execution[name].get("error") is not None
        or execution[name].get("timed_out") not in (None, False)
        or execution[name].get("cancelled") not in (None, False)
        for name in ("platform", "linkage")
    ):
        return Qualification.UNVERIFIED
    # Probe attestations are scoped to this Run as well. A successful exit
    # from another Run cannot qualify the current incident lifecycle.
    for probe_name in ("platform", "linkage"):
        probe = execution[probe_name]
        if "run_id" in probe and (type(probe["run_id"]) is not str or probe["run_id"] != run_id):
            return Qualification.UNVERIFIED
    blocked = receipt.get("blocking")
    if not isinstance(blocked, list) or any(type(name) is not str for name in blocked):
        return Qualification.UNVERIFIED
    if set(blocked) != {
        name for name, item in by_name.items() if item["status"] == "HOLD"
    } or len(blocked) != len(set(blocked)):
        return Qualification.UNVERIFIED
    # Missing evidence is not a functional failure. A HOLD claim cannot
    # upgrade an UNVERIFIED check to a diagnosed failing component.
    if any(item["status"] == "UNVERIFIED" for item in by_name.values()):
        return Qualification.UNVERIFIED
    if any(item["status"] == "HOLD" for item in by_name.values()):
        return Qualification.HOLD if receipt.get("verdict") == "HOLD" else Qualification.UNVERIFIED
    if receipt.get("verdict") != "PASS":
        return Qualification.UNVERIFIED
    return Qualification.PASS_CLAIM_ONLY
