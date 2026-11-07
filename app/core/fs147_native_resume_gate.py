"""FS147 pure native-HITL and fencing gate; NEVER dispatches Temporal or mutates GLPI.

All observations must be freshly authenticated and acquired by the adapter.
A True result is necessary, never sufficient, for a side effect.
"""
from dataclasses import dataclass
from .fs364_dispatch_boundary import dispatch_boundary_ok
from .fs364_outbox_transition import OutboxRecord
from .fs364_outbox_envelope import ResumeEnvelope


@dataclass(frozen=True)
class NativeApproval:
    ticket_id: int
    tenant_id: str
    run_id: str
    action_id: str
    path: str
    content_fingerprint: str
    validation_id: str
    validator_id: str
    requester_id: str
    expires_at_epoch: int
    decision: str
    verified_native: bool


@dataclass(frozen=True)
class Fencing:
    event_id: str
    owner_id: str
    token: int
    current_token: int
    lease_expires_epoch: int
    db_verified: bool


def native_resume_gate(record, admitted, current, admitted_state, current_state,
                       approval, fencing, *, action_id, path,
                       content_fingerprint, now_epoch, expected_revision, expected_owner_id=None,
                       authoritative_read=False):
    """Fail closed on UNKNOWN, stale lease, wrong action, revocation or LIVE."""
    if (not isinstance(record, OutboxRecord)
            or not isinstance(current, ResumeEnvelope)
            or not isinstance(approval, NativeApproval)
            or not isinstance(fencing, Fencing)):
        return False
    if type(now_epoch) is not int or now_epoch < 0:
        return False
    if any(type(x) is not int for x in (
        approval.ticket_id, approval.expires_at_epoch, fencing.token,
        fencing.current_token, fencing.lease_expires_epoch)):
        return False
    if any(type(x) is not str or not x or x != x.strip() or
           not x.isprintable() or any(c.isspace() for c in x)
           for x in (action_id, path, content_fingerprint, expected_owner_id,
                     approval.tenant_id, approval.run_id, approval.action_id,
                     approval.path, approval.content_fingerprint,
                     approval.validation_id, approval.validator_id,
                     approval.requester_id, fencing.event_id, fencing.owner_id)):
        return False
    if (approval.verified_native is not True or fencing.db_verified is not True
            or approval.decision != "ACCEPTED" or approval.ticket_id != 147
            or approval.validator_id == approval.requester_id
            or approval.expires_at_epoch <= now_epoch
            or fencing.lease_expires_epoch <= now_epoch
            or fencing.token <= 0 or fencing.token != fencing.current_token
            or fencing.event_id != record.event_id
            or fencing.owner_id != expected_owner_id
            or approval.tenant_id != current.tenant_id
            or approval.run_id != current.run_id
            or approval.action_id != action_id or approval.path != path
            or approval.content_fingerprint != content_fingerprint):
        return False
    return dispatch_boundary_ok(
        record, admitted, current, admitted_state, current_state,
        expected_revision=expected_revision,
        authoritative_read=authoritative_read, lease_owned=True)
