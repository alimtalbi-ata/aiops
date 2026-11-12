"""FS147 native HITL scope check, pure and fail closed.

A native approval is not a launch permit. The caller must authenticate its
source and re-read it under the same transactional fencing boundary.
"""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
from hmac import compare_digest


class ScopeDecision(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    SCOPE_MATCH = "SCOPE_MATCH"


@dataclass(frozen=True)
class ApprovalScope:
    ticket_id: int
    run_id: str
    action_id: str
    path: str
    content_sha256: str
    requester_id: str
    validator_id: str
    status: str
    expires_at: datetime
    native_authenticated: bool
    durable_read: bool


def classify_approval_scope(approval: ApprovalScope | None, *,
                            ticket_id: int, run_id: str, action_id: str,
                            path: str, content_sha256: str,
                            requester_id: str, now: datetime) -> ScopeDecision:
    """SCOPE_MATCH means matching evidence only; never dispatch or resume."""
    if type(ticket_id) is int and ticket_id != 147:
        return ScopeDecision.DENIED
    if not isinstance(approval, ApprovalScope):
        return ScopeDecision.UNKNOWN
    if type(approval.ticket_id) is int and approval.ticket_id != 147:
        return ScopeDecision.DENIED
    if approval.status == "REJECTED":
        return ScopeDecision.DENIED
    if approval.status == "PENDING":
        return ScopeDecision.NEEDS_HUMAN
    values = (run_id, action_id, path, content_sha256, requester_id,
              approval.run_id, approval.action_id, approval.path,
              approval.content_sha256, approval.requester_id, approval.validator_id)
    if (type(ticket_id) is not int or type(approval.ticket_id) is not int or
        any(type(v) is not str or not v or v.strip() != v or len(v) > 512 or
            any(ord(c) < 32 or ord(c) == 127 or
                __import__("unicodedata").category(c) == "Cf" for c in v)
            for v in values)):
        return ScopeDecision.UNKNOWN
    if (type(content_sha256) is not str or len(content_sha256) != 64 or
        any(c not in "0123456789abcdef" for c in content_sha256) or
        type(approval.content_sha256) is not str or
        len(approval.content_sha256) != 64 or
        any(c not in "0123456789abcdef" for c in approval.content_sha256)):
        return ScopeDecision.UNKNOWN
    if (type(approval.native_authenticated) is not bool or
        type(approval.durable_read) is not bool or
        not approval.native_authenticated or not approval.durable_read):
        return ScopeDecision.UNKNOWN
    if (not isinstance(now, datetime) or not isinstance(approval.expires_at, datetime)
        or now.tzinfo is None or approval.expires_at.tzinfo is None
        or now.utcoffset() is None or approval.expires_at.utcoffset() is None):
        return ScopeDecision.UNKNOWN
    if approval.status != "ACCEPTED":
        return ScopeDecision.UNKNOWN
    if approval.validator_id == requester_id or approval.validator_id == approval.requester_id:
        return ScopeDecision.DENIED
    if now.astimezone(timezone.utc) >= approval.expires_at.astimezone(timezone.utc):
        return ScopeDecision.DENIED
    if (ticket_id != approval.ticket_id or run_id != approval.run_id or
        action_id != approval.action_id or path != approval.path or
        requester_id != approval.requester_id or
        not compare_digest(content_sha256, approval.content_sha256)):
        return ScopeDecision.DENIED
    return ScopeDecision.SCOPE_MATCH
