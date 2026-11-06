"""FS.364 pure outbox acknowledgement protocol; no network or database I/O.

Persist transitions with compare-and-swap (event_id, revision) and unique
(tenant_id, idempotency_key). Temporal must deduplicate by deterministic
workflow/signal identity; acknowledgement alone is not proof of delivery.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class OutboxRecord:
    event_id: str
    revision: int
    status: str
    attempt: int
    tenant_id: str
    idempotency_key: str
    ticket_id: int
    mode: str


@dataclass(frozen=True)
class Transition:
    status: str
    record: OutboxRecord | None


def transition(record: OutboxRecord, *, expected_revision: int,
               action: str, revalidated: bool = False) -> Transition:
    """Fail closed; caller must CAS persist result before any dispatch.

    CLAIM is a lease claim only; actual Temporal delivery requires a fresh
    authoritative Policy/HITL/GLPI read and idempotent workflow signal.
    """
    if not isinstance(record, OutboxRecord):
        return Transition("DENIED", None)
    if (type(record.revision) is not int or record.revision < 0
            or type(expected_revision) is not int
            or record.revision != expected_revision
            or type(record.attempt) is not int or record.attempt < 0
            or type(record.ticket_id) is not int or record.ticket_id != 147
            or record.mode != "DEMO"
            or not all(isinstance(v, str) and v and v == v.strip()
                       and v.isprintable() and not any(c.isspace() for c in v)
                       for v in (record.event_id, record.tenant_id,
                                 record.idempotency_key))):
        return Transition("DENIED", None)
    if action == "CLAIM" and record.status == "PENDING":
        return Transition("CLAIMED", OutboxRecord(
            record.event_id, record.revision + 1, "CLAIMED",
            record.attempt + 1, record.tenant_id,
            record.idempotency_key, 147, "DEMO"))
    if action == "ACK" and record.status == "CLAIMED" and revalidated is True:
        return Transition("ACKED", OutboxRecord(
            record.event_id, record.revision + 1, "ACKED",
            record.attempt, record.tenant_id,
            record.idempotency_key, 147, "DEMO"))
    if action == "REQUEUE" and record.status == "CLAIMED":
        return Transition("REQUEUED", OutboxRecord(
            record.event_id, record.revision + 1, "PENDING",
            record.attempt, record.tenant_id,
            record.idempotency_key, 147, "DEMO"))
    return Transition("DENIED", None)
