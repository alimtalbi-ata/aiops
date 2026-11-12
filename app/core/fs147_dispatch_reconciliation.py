"""FS147 durable dispatch reconciliation. Pure decisions; no Temporal/GLPI I/O.

A committed outbox row is not proof of Temporal delivery. In particular, a
crash after signal but before receipt leaves delivery UNKNOWN: never re-send
blindly. A human/operator or authoritative Temporal reconciliation is needed.
"""
from dataclasses import dataclass
from enum import Enum


class ReconcileStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ALREADY_RECORDED = "ALREADY_RECORDED"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class DispatchSnapshot:
    tenant_id: str
    idempotency_key: str
    run_id: str
    workflow_id: str
    action_id: str
    approval_id: str
    fence_token: int
    ticket_id: int
    mode: str


def classify_dispatch(snapshot, *, outbox_state=None, temporal_receipt=None,
                      authoritative_read=None, policy=None, approval=None,
                      stop_auto=None, fence_current=None):
    """Classify only; caller must perform atomic CAS and native HITL re-read."""
    if not isinstance(snapshot, DispatchSnapshot):
        return ReconcileStatus.UNKNOWN
    fields = ("tenant_id", "idempotency_key", "run_id", "workflow_id",
              "action_id", "approval_id")
    if not all(type(getattr(snapshot, k)) is str and getattr(snapshot, k).strip()
               for k in fields):
        return ReconcileStatus.UNKNOWN
    if type(snapshot.fence_token) is not int or snapshot.fence_token <= 0:
        return ReconcileStatus.UNKNOWN
    if type(snapshot.ticket_id) is not int or type(snapshot.mode) is not str:
        return ReconcileStatus.UNKNOWN
    if snapshot.mode != "DEMO" or snapshot.ticket_id != 147:
        return ReconcileStatus.DENIED
    if stop_auto is True or policy in ("DENY", "BLOCKED") or approval in ("REJECTED", "EXPIRED"):
        return ReconcileStatus.DENIED
    if approval == "PENDING":
        return ReconcileStatus.NEEDS_HUMAN
    if any(type(x) is not bool for x in (authoritative_read, stop_auto, fence_current)):
        return ReconcileStatus.UNKNOWN
    if not authoritative_read or not fence_current or policy != "ALLOW" or approval != "ACCEPTED":
        return ReconcileStatus.UNKNOWN
    if type(temporal_receipt) is not bool:
        return ReconcileStatus.UNKNOWN
    if outbox_state == "DELIVERED":
        return (ReconcileStatus.ALREADY_RECORDED if temporal_receipt
                else ReconcileStatus.UNKNOWN)
    if outbox_state in ("DISPATCHING", "UNCERTAIN"):
        return ReconcileStatus.UNKNOWN
    if outbox_state != "PENDING":
        return ReconcileStatus.UNKNOWN
    if temporal_receipt:
        return ReconcileStatus.ALREADY_RECORDED
    return ReconcileStatus.ELIGIBLE_FOR_REVALIDATION
