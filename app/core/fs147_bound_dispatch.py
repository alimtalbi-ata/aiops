"""FS147 receipt identity guard. Pure, side-effect-free, fail-closed.

A boolean Temporal receipt is insufficient to prove that *this* action was
recorded. Require a verified, identity-bound receipt before classifying a
dispatch as already recorded or eligible for revalidation.
"""
from dataclasses import dataclass
from enum import Enum

from app.core.fs147_dispatch_reconciliation import (
    DispatchSnapshot, ReconcileStatus, classify_dispatch,
)


class BoundStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    CONFLICT = "CONFLICT"
    ALREADY_RECORDED = "ALREADY_RECORDED"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class BoundReceipt:
    tenant_id: str
    idempotency_key: str
    run_id: str
    workflow_id: str
    action_id: str
    approval_id: str
    fence_token: int
    ticket_id: int
    mode: str


def classify_bound_dispatch(snapshot, *, receipt=None, receipt_verified=None,
                            absence_verified=None, **dispatch_observations):
    """Classify only: neither a Temporal signal nor a PG16 CAS.

    Receipt verification and absence verification MUST come from an
    authenticated, authoritative adapter. They are not inferred from caches.
    A missing receipt after a dispatch attempt is not authoritative absence.
    """
    if not isinstance(snapshot, DispatchSnapshot):
        return BoundStatus.UNKNOWN
    base = classify_dispatch(
        snapshot, temporal_receipt=False, **dispatch_observations
    )
    if base == ReconcileStatus.DENIED:
        return BoundStatus.DENIED
    if base == ReconcileStatus.NEEDS_HUMAN:
        return BoundStatus.NEEDS_HUMAN
    if base == ReconcileStatus.UNKNOWN and dispatch_observations.get("outbox_state") not in (
        "DISPATCHING", "UNCERTAIN", "DELIVERED", "PENDING"
    ):
        return BoundStatus.UNKNOWN
    if type(receipt_verified) is not bool or type(absence_verified) is not bool:
        return BoundStatus.UNKNOWN
    if receipt_verified and absence_verified:
        return BoundStatus.UNKNOWN
    if receipt is not None:
        if not isinstance(receipt, BoundReceipt) or not receipt_verified:
            return BoundStatus.UNKNOWN
        fields = ("tenant_id", "idempotency_key", "run_id", "workflow_id",
                  "action_id", "approval_id", "fence_token", "ticket_id", "mode")
        if any(getattr(snapshot, field) != getattr(receipt, field) for field in fields):
            return BoundStatus.CONFLICT
        # Explicit denials and missing policy/fencing authority take precedence.
        if base == ReconcileStatus.UNKNOWN and dispatch_observations.get("outbox_state") == "PENDING":
            return BoundStatus.UNKNOWN
        if dispatch_observations.get("outbox_state") in ("DISPATCHING", "UNCERTAIN"):
            return BoundStatus.UNKNOWN
        return BoundStatus.ALREADY_RECORDED if base in (
            ReconcileStatus.ELIGIBLE_FOR_REVALIDATION, ReconcileStatus.ALREADY_RECORDED
        ) else BoundStatus.UNKNOWN
    if receipt_verified:
        return BoundStatus.UNKNOWN
    if not absence_verified:
        return BoundStatus.UNKNOWN
    if dispatch_observations.get("outbox_state") != "PENDING":
        return BoundStatus.UNKNOWN
    return (BoundStatus.ELIGIBLE_FOR_REVALIDATION
            if base == ReconcileStatus.ELIGIBLE_FOR_REVALIDATION
            else BoundStatus.UNKNOWN)
