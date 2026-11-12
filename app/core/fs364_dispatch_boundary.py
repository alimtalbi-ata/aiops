"""FS.364 side-effect-free dispatch boundary for an already-linked GLPI 147.

This predicate is not a Temporal dispatcher or an authorization to perform
an effect. The caller must read authoritative snapshots, own a PG16 outbox
lease, revalidate under concurrency control and deduplicate Temporal delivery.
"""
from .fs364_outbox_envelope import ResumeEnvelope, envelope_still_admissible
from .fs364_dispatch_guard import DispatchState
from .fs364_outbox_transition import OutboxRecord


def dispatch_boundary_ok(
    record: OutboxRecord,
    admitted: ResumeEnvelope,
    current: ResumeEnvelope,
    admitted_state: DispatchState,
    current_state: DispatchState,
    *,
    expected_revision: int,
    authoritative_read: bool,
    lease_owned: bool,
) -> bool:
    """Fail closed for a CLAIMED DEMO event; never emit a signal."""
    if (not isinstance(record, OutboxRecord)
            or not isinstance(admitted, ResumeEnvelope)
            or not isinstance(current, ResumeEnvelope)
            or type(expected_revision) is not int
            or type(record.revision) is not int
            or record.revision != expected_revision
            or record.status != "CLAIMED"
            or type(record.attempt) is not int or record.attempt < 1
            or authoritative_read is not True
            or lease_owned is not True):
        return False
    if (record.mode != "DEMO" or type(record.ticket_id) is not int
            or record.ticket_id != 147
            or record.tenant_id != current.tenant_id
            or record.idempotency_key != current.idempotency_key):
        return False
    return envelope_still_admissible(
        admitted, current, admitted_state, current_state
    )
