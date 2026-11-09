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
        # compare_digest(str, str) raises TypeError for non-ASCII identifiers.
        # Refuse malformed scope rather than turning a denial into an exception.
        try:
            value_bytes = value.encode("ascii")
        except UnicodeEncodeError:
            return deny("INVALID_INTENT")
        if not isinstance(other, str):
            return deny("APPROVAL_MISMATCH")
        try:
            other_bytes = other.encode("ascii")
        except UnicodeEncodeError:
            return deny("APPROVAL_MISMATCH")
        if not hmac.compare_digest(value_bytes, other_bytes):
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
    issued = approval.get("issued_at")
    if not isinstance(issued, str):
        return deny("ISSUED_AT_UNVERIFIED")
    try:
        issued_dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
    except ValueError:
        return deny("ISSUED_AT_UNVERIFIED")
    if issued_dt.tzinfo is None or issued_dt.utcoffset() is None:
        return deny("ISSUED_AT_UNVERIFIED")
    issued_utc = issued_dt.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    expiry_utc = parsed.astimezone(timezone.utc)
    if expiry_utc <= now_utc:
        return deny("APPROVAL_EXPIRED")
    if issued_utc > now_utc or expiry_utc <= issued_utc:
        return deny("APPROVAL_TIME_INVALID")
    if expiry_utc - issued_utc > timedelta(minutes=10):
        return deny("APPROVAL_HORIZON_EXCEEDED")
    remaining = expiry_utc - now_utc
    if remaining <= timedelta(0):
        return deny("APPROVAL_EXPIRED")
    # A long-lived approval cannot be replayed indefinitely after Policy changes.
    # The maximum horizon is intentionally conservative for this dry-run gate.
    if remaining > timedelta(minutes=10):
        return deny("APPROVAL_HORIZON_EXCEEDED")
    return {"status": "BOUND_READ_ONLY", "reason": "DRY_RUN_ONLY", "dispatch_allowed": False}
