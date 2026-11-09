"""Pure action-bound HITL admission; no IO, no dispatch or durable claim."""
import hmac
import re
from datetime import datetime, timezone, timedelta

_SHA = re.compile(r"[0-9a-f]{64}\Z")

def check_action_binding(intent, approval, *, now):
    def deny(reason):
        return {"status": "UNKNOWN", "reason": reason, "dispatch_allowed": False}
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return deny("CLOCK_UNVERIFIED")
    if not isinstance(intent, dict) or not isinstance(approval, dict):
        return deny("BINDING_MISSING")
    fields = ("tenant_id", "run_id", "action_id", "target", "parameters_digest", "policy_revision")
    for field in fields:
        value = intent.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            return deny("INVALID_INTENT")
        other = approval.get(field)
        if not isinstance(other, str) or not hmac.compare_digest(value, other):
            return deny("APPROVAL_MISMATCH")
    if _SHA.fullmatch(intent["parameters_digest"]) is None:
        return deny("INVALID_DIGEST")
    if intent.get("dry_run") is not True or approval.get("decision") != "APPROVED":
        return deny("LIVE_OR_REFUSED")
    if approval.get("authenticated") is not True:
        return deny("AUTHENTICATION_UNVERIFIED")
    expiry = approval.get("expires_at")
    if not isinstance(expiry, str):
        return deny("EXPIRY_UNVERIFIED")
    try:
        parsed = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except ValueError:
        return deny("EXPIRY_UNVERIFIED")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return deny("EXPIRY_UNVERIFIED")
    remaining = parsed.astimezone(timezone.utc) - now.astimezone(timezone.utc)
    if remaining <= timedelta(0):
        return deny("APPROVAL_EXPIRED")
    # A long-lived approval cannot be replayed indefinitely after Policy changes.
    # The maximum horizon is intentionally conservative for this dry-run gate.
    if remaining > timedelta(minutes=10):
        return deny("APPROVAL_HORIZON_EXCEEDED")
    return {"status": "BOUND_READ_ONLY", "reason": "DRY_RUN_ONLY", "dispatch_allowed": False}
