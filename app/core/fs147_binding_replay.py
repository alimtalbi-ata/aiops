"""FS147 persisted-binding replay admission, pure and fail-closed.

This is a comparison of supplied snapshots, not a database transaction or a
permission to create GLPI tickets, start runs, or signal Temporal.
"""
from dataclasses import dataclass
from enum import Enum
from .fs147_binding_key import derive_fs147_key, KeyStatus


class ReplayDecision(str, Enum):
    SAME_BINDING = "SAME_BINDING"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


@dataclass(frozen=True)
class BindingSnapshot:
    tenant_id: object
    alert_fingerprint: object
    incident_id: object
    run_id: object
    evidence_id: object
    ticket_id: object
    mode: object
    key: object


def classify_binding_replay(requested: object, persisted: object,
                            *, authoritative_read: object) -> ReplayDecision:
    """Compare full identities, never key alone.

    SAME_BINDING is observational only. Callers must use a unique constraint,
    serializable transaction or equivalent CAS and re-read the committed row.
    """
    if not isinstance(requested, BindingSnapshot):
        return ReplayDecision.UNKNOWN
    r = derive_fs147_key(
        tenant_id=requested.tenant_id, alert_fingerprint=requested.alert_fingerprint,
        incident_id=requested.incident_id, run_id=requested.run_id,
        evidence_id=requested.evidence_id, ticket_id=requested.ticket_id,
        mode=requested.mode,
    )
    if r.status is KeyStatus.DENIED:
        return ReplayDecision.DENIED
    if r.status is not KeyStatus.READY:
        return ReplayDecision.UNKNOWN
    if type(authoritative_read) is not bool or not authoritative_read:
        return ReplayDecision.UNKNOWN
    if not isinstance(persisted, BindingSnapshot):
        return ReplayDecision.UNKNOWN
    p = derive_fs147_key(
        tenant_id=persisted.tenant_id, alert_fingerprint=persisted.alert_fingerprint,
        incident_id=persisted.incident_id, run_id=persisted.run_id,
        evidence_id=persisted.evidence_id, ticket_id=persisted.ticket_id,
        mode=persisted.mode,
    )
    if p.status is not KeyStatus.READY:
        return ReplayDecision.UNKNOWN
    if type(requested.key) is not str or type(persisted.key) is not str:
        return ReplayDecision.UNKNOWN
    if requested.key != r.key or persisted.key != p.key:
        return ReplayDecision.CONFLICT
    identity = lambda b: (b.tenant_id, b.alert_fingerprint, b.incident_id,
                          b.run_id, b.evidence_id, b.ticket_id, b.mode)
    if identity(requested) != identity(persisted):
        return ReplayDecision.CONFLICT
    return ReplayDecision.SAME_BINDING
