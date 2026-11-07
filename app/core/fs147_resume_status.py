"""FS147 explicit non-executable outcome classification for native resume checks.

UNKNOWN is not an approval. This module never calls GLPI, Policy or Temporal.
"""
from dataclasses import dataclass
from enum import Enum


class ResumeStatus(str, Enum):
    DENIED = "DENIED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    UNKNOWN = "UNKNOWN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class ResumeObservation:
    mode: str
    ticket_id: int
    policy: str
    stop_auto: bool
    approval: str
    action_bound: bool
    owner_verified: bool
    fencing_verified: bool
    temporal_state: str
    authoritative_read: bool


def classify_resume(observation):
    """Pure fail-closed triage, not a permission to launch or resume.

    A positive result requires a separate transactional revalidation immediately
    before any side effect. Missing and mistyped observations remain UNKNOWN.
    """
    if not isinstance(observation, ResumeObservation):
        return ResumeStatus.UNKNOWN
    o = observation
    if (type(o.mode) is not str or type(o.ticket_id) is not int
            or type(o.policy) is not str or type(o.approval) is not str
            or type(o.temporal_state) is not str
            or any(type(x) is not bool for x in (
                o.stop_auto, o.action_bound, o.owner_verified,
                o.fencing_verified, o.authoritative_read))):
        return ResumeStatus.UNKNOWN
    if o.mode == "LIVE" or o.ticket_id != 147 or o.policy in ("DENY", "BLOCKED") or o.stop_auto:
        return ResumeStatus.DENIED
    if o.mode != "DEMO" or o.policy != "ALLOW":
        return ResumeStatus.UNKNOWN
    if o.approval in ("REJECTED", "EXPIRED"):
        return ResumeStatus.DENIED
    if o.approval == "PENDING":
        return ResumeStatus.NEEDS_HUMAN
    if o.approval != "ACCEPTED":
        return ResumeStatus.UNKNOWN
    if not o.action_bound:
        return ResumeStatus.DENIED
    if o.temporal_state not in ("WAITING_HUMAN", "CANCELLED", "COMPLETED"):
        return ResumeStatus.UNKNOWN
    if o.temporal_state != "WAITING_HUMAN":
        return ResumeStatus.DENIED
    if not (o.owner_verified and o.fencing_verified and o.authoritative_read):
        return ResumeStatus.UNKNOWN
    return ResumeStatus.ELIGIBLE_FOR_REVALIDATION
