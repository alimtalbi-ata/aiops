"""FS147 authoritative absence guard for idempotent GLPI-147 correlation.

Pure classification only. No DB, GLPI, Temporal, or other IO.
An absent record is UNKNOWN unless its absence was verified by an authoritative
tenant-scoped transactional read. NEW never authorizes a write.
"""
from enum import Enum

from .fs147_immutable_link import LinkDecision, classify_link


class Admission(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEW_CANDIDATE = "NEW_CANDIDATE"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


def classify_authoritative_link(candidate, existing=None, *, absence_verified=False,
                                existing_verified=False):
    """Never turn missing evidence or a cache miss into an authorized creation.

    The adapter must enforce UNIQUE(tenant_id, idempotency_key), lock/recheck
    before insert, and return the persisted row for a competing transaction.
    These booleans are claims from the adapter, not authentication proofs.
    """
    if type(absence_verified) is not bool or type(existing_verified) is not bool:
        return Admission.UNKNOWN
    result = classify_link(candidate, existing)
    if result == LinkDecision.DENIED:
        return Admission.DENIED
    if result == LinkDecision.UNKNOWN:
        return Admission.UNKNOWN
    if existing is None:
        if existing_verified or not absence_verified:
            return Admission.UNKNOWN
        return Admission.NEW_CANDIDATE
    if absence_verified or not existing_verified:
        return Admission.UNKNOWN
    if result == LinkDecision.REPLAY:
        return Admission.REPLAY
    return Admission.CONFLICT
