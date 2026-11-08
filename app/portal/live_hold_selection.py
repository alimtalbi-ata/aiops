"""Select actionable Portal HOLDs from a fresh, read-only Debian use-case receipt.

This module never authorizes actions, resolves incidents or calls a backend.
"""
from .live_receipt import portal_usecase_status

PORTAL_OWNERS = frozenset(("portal", "frontend", "browser", "ui"))
SAFE_POLICY_REASONS = frozenset(("policy_denied", "hitl_pending", "approval_required"))
NON_PORTAL_COMPONENTS = frozenset(("policy", "hitl", "approval", "policy-engine",
                                    "core", "worker", "temporal", "evidence",
                                    "intelligence", "critic", "twin", "itsm", "glpi"))
SAFE_POLICY_STATES = frozenset(("denied", "rejected", "pending", "approval_required", "hitl_pending",
                                "awaiting_approval", "awaiting_human_approval", "blocked_by_policy",
                                "policy_blocked", "approval_pending"))


def _safe_policy_reason(reason):
    """Recognize explicit safe-policy reason codes, including qualified details.

    A prefix must end at a token boundary; e.g. policy_denied_extra is NOT
    a Policy denial. Never infer a denial from arbitrary free text.
    """
    return any(reason == code or reason.startswith(code + separator)
               for code in SAFE_POLICY_REASONS for separator in (":", " ", ";", "|"))


def first_portal_hold(receipt, now_utc):
    """Return the first explicitly Portal-owned HOLD, or a fail-closed reason.

    A missing/stale receipt is not a failed E2E test. A Policy denial is
    deliberately not reclassified as a Portal defect.
    """
    verdict = portal_usecase_status(receipt, now_utc)
    if verdict["status"] != "HOLD":
        return {"status": verdict["status"], "reason": verdict["reason"], "hold": None}
    for check in receipt["checks"]:
        if not isinstance(check, dict) or check.get("status") != "HOLD":
            continue
        owner = str(check.get("owner") or check.get("component") or "").strip().lower()
        component = str(check.get("component") or "").strip().lower()
        reason = str(check.get("reason") or "").strip().lower()
        policy_states = {str(check.get(key) or "").strip().lower()
                         for key in ("policy_status", "policy_state", "hitl_status", "hitl_state")}
        if (owner in PORTAL_OWNERS and component not in NON_PORTAL_COMPONENTS
                and not _safe_policy_reason(reason) and policy_states.isdisjoint(SAFE_POLICY_STATES)):
            return {"status": "HOLD", "reason": "portal_hold", "hold": {
                "id": str(check.get("id") or "unknown"),
                "reason": str(check.get("reason") or "unspecified")}}
    return {"status": "UNVERIFIED", "reason": "no_actionable_portal_hold", "hold": None}
