"""FS147 launch preflight: pure triage, never an execution authorization.

No GLPI writes, Temporal signals, network, filesystem, or policy bypass.
A positive result only permits authoritative transactional revalidation.
"""
from dataclasses import dataclass
from enum import Enum


class LaunchStatus(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class LaunchSnapshot:
    mode: str
    tenant_id: str
    idempotency_key: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    evidence_sha256: str
    glpi_ticket_id: int
    ticket_exists_verified: bool
    policy: str
    stop_auto: bool
    hitl: str
    hitl_action_bound: bool
    ownership_verified: bool
    fencing_verified: bool
    temporal_state: str
    authoritative_read: bool


def classify_launch(snapshot):
    """Fail closed. Unknown observations cannot become approvals."""
    if not isinstance(snapshot, LaunchSnapshot):
        return LaunchStatus.UNKNOWN
    s = snapshot
    strings = (s.mode, s.tenant_id, s.idempotency_key,
               s.alert_fingerprint, s.incident_id, s.run_id, s.evidence_id,
               s.evidence_sha256, s.policy, s.hitl, s.temporal_state)
    flags = (s.ticket_exists_verified, s.stop_auto, s.hitl_action_bound,
             s.ownership_verified, s.fencing_verified, s.authoritative_read)
    if (any(type(v) is not str or not v.strip() for v in strings)
            or any(type(v) is not bool for v in flags)
            or type(s.glpi_ticket_id) is not int):
        return LaunchStatus.UNKNOWN
    if (s.mode == "LIVE" or s.glpi_ticket_id != 147
            or s.policy in ("DENY", "BLOCKED") or s.stop_auto
            or s.hitl in ("REJECTED", "EXPIRED")
            or s.temporal_state in ("CANCELLED", "COMPLETED")):
        return LaunchStatus.DENIED
    if s.mode != "DEMO" or s.policy != "ALLOW":
        return LaunchStatus.UNKNOWN
    if s.hitl == "PENDING":
        return LaunchStatus.NEEDS_HUMAN
    if s.hitl != "ACCEPTED" or s.temporal_state != "WAITING_HUMAN":
        return LaunchStatus.UNKNOWN
    if not s.hitl_action_bound:
        return LaunchStatus.DENIED
    if not (s.ticket_exists_verified and s.ownership_verified
            and s.fencing_verified and s.authoritative_read):
        return LaunchStatus.UNKNOWN
    return LaunchStatus.ELIGIBLE_FOR_REVALIDATION
