"""FS147 Temporal signal admission: pure replay classification, never dispatch.

A matching receipt means the signal was previously recorded, not that the
workflow resumed or the underlying action succeeded.
"""
from dataclasses import dataclass
from enum import Enum


class SignalStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    NEW_CANDIDATE = "NEW_CANDIDATE"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class SignalIntent:
    tenant_id: str
    idempotency_key: str
    run_id: str
    workflow_id: str
    action_id: str
    approval_id: str
    fence_token: int
    mode: str
    ticket_id: int


def _valid(x):
    return (isinstance(x, SignalIntent)
            and all(type(getattr(x, f)) is str and bool(getattr(x, f).strip())
                    for f in ("tenant_id", "idempotency_key", "run_id",
                              "workflow_id", "action_id", "approval_id"))
            and type(x.fence_token) is int and x.fence_token > 0
            and type(x.mode) is str and type(x.ticket_id) is int)


def classify_signal(intent, receipt=None, *, authoritative_absence=False,
                    authoritative_receipt=False, temporal_state=None,
                    policy=None, approval=None, stop_auto=None):
    """Fail closed until a transactional outbox adapter rechecks all inputs.

    The adapter must lock the (tenant, idempotency_key) row, enforce uniqueness,
    CAS the fence and commit the receipt before signalling Temporal.
    This predicate performs none of those operations.
    """
    if not _valid(intent):
        return SignalStatus.UNKNOWN
    if intent.mode != "DEMO" or intent.ticket_id != 147:
        return SignalStatus.DENIED
    if (type(authoritative_absence) is not bool
            or type(authoritative_receipt) is not bool
            or type(stop_auto) is not bool):
        return SignalStatus.UNKNOWN
    if stop_auto or policy in ("DENY", "BLOCKED") or approval in ("REJECTED", "EXPIRED"):
        return SignalStatus.DENIED
    if policy != "ALLOW":
        return SignalStatus.UNKNOWN
    if approval == "PENDING":
        return SignalStatus.NEEDS_HUMAN
    if approval != "ACCEPTED":
        return SignalStatus.UNKNOWN
    if receipt is not None:
        if not _valid(receipt) or not authoritative_receipt or authoritative_absence:
            return SignalStatus.UNKNOWN
        if (intent.tenant_id, intent.idempotency_key) != (receipt.tenant_id, receipt.idempotency_key):
            return SignalStatus.CONFLICT
        return SignalStatus.REPLAY if intent == receipt else SignalStatus.CONFLICT
    if authoritative_receipt or not authoritative_absence:
        return SignalStatus.UNKNOWN
    if temporal_state in ("COMPLETED", "CANCELLED", "TERMINATED"):
        return SignalStatus.DENIED
    if temporal_state != "WAITING_HUMAN":
        return SignalStatus.UNKNOWN
    return SignalStatus.NEW_CANDIDATE
