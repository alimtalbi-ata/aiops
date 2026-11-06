"""FS.364: pure acknowledgement gate; never contacts GLPI or Temporal.

A transport acknowledgement is not proof of workflow execution. Callers must
persist the receipt and outbox CAS in one transaction; Temporal signal IDs must
be deduplicated at the receiver. No LIVE dispatch is permitted here.
"""
from dataclasses import dataclass

from .fs364_outbox_transition import OutboxRecord


@dataclass(frozen=True)
class DeliveryReceipt:
    event_id: str
    tenant_id: str
    idempotency_key: str
    workflow_id: str
    signal_id: str
    ticket_id: int
    mode: str
    accepted: bool


def ack_receipt_matches(record: OutboxRecord, receipt: DeliveryReceipt,
                        *, expected_revision: int) -> bool:
    """Require a positive, exact receipt before a caller considers ACK."""
    if not isinstance(record, OutboxRecord) or not isinstance(receipt, DeliveryReceipt):
        return False
    if (record.status != "CLAIMED" or record.mode != "DEMO"
            or type(record.ticket_id) is not int or record.ticket_id != 147
            or type(record.revision) is not int or record.revision < 0
            or type(expected_revision) is not int
            or record.revision != expected_revision
            or type(record.attempt) is not int or record.attempt < 1
            or receipt.accepted is not True or receipt.mode != "DEMO"
            or type(receipt.ticket_id) is not int or receipt.ticket_id != 147):
        return False
    fields = (record.event_id, record.tenant_id, record.idempotency_key,
              receipt.workflow_id, receipt.signal_id)
    if not all(type(s) is str and s and s == s.strip()
               and s.isprintable() and not any(c.isspace() for c in s)
               for s in fields):
        return False
    return (receipt.event_id == record.event_id
            and receipt.tenant_id == record.tenant_id
            and receipt.idempotency_key == record.idempotency_key)
