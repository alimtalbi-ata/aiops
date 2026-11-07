"""FS147 evidence provenance admission; pure and fail-closed.

A digest alone cannot attest that evidence belongs to a run. This module
requires an independent, authenticated, read-only observation before reuse.
No GLPI, DB, Temporal or host effects.
"""
from dataclasses import dataclass
from enum import Enum
from hmac import compare_digest


class EvidenceStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"
    CONFLICT = "CONFLICT"
    MATCH = "MATCH"


@dataclass(frozen=True)
class EvidenceBinding:
    tenant_id: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    evidence_sha256: str
    ticket_id: int
    mode: str


@dataclass(frozen=True)
class EvidenceObservation:
    binding: EvidenceBinding
    authenticated_read: bool
    durable_read: bool


def classify_evidence_binding(expected, observed):
    """MATCH proves identity coherence only, never execution authorization."""
    if not isinstance(expected, EvidenceBinding):
        return EvidenceStatus.UNKNOWN
    if expected.mode == "LIVE" or type(expected.ticket_id) is int and expected.ticket_id != 147:
        return EvidenceStatus.DENIED
    if expected.mode != "DEMO" or type(expected.ticket_id) is not int:
        return EvidenceStatus.UNKNOWN
    if not isinstance(observed, EvidenceObservation):
        return EvidenceStatus.UNKNOWN
    if type(observed.authenticated_read) is not bool or type(observed.durable_read) is not bool:
        return EvidenceStatus.UNKNOWN
    if not observed.authenticated_read or not observed.durable_read:
        return EvidenceStatus.UNKNOWN
    actual = observed.binding
    if not isinstance(actual, EvidenceBinding):
        return EvidenceStatus.UNKNOWN
    if actual.mode == "LIVE" or type(actual.ticket_id) is int and actual.ticket_id != 147:
        return EvidenceStatus.DENIED
    if actual.mode != "DEMO" or type(actual.ticket_id) is not int:
        return EvidenceStatus.UNKNOWN
    fields = ("tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id")
    for item in (expected, actual):
        if any(type(getattr(item, field)) is not str or
               not getattr(item, field) or
               getattr(item, field).strip() != getattr(item, field) or
               any(ord(ch) < 32 or ord(ch) == 127 for ch in getattr(item, field)) or
               len(getattr(item, field)) > 512
               for field in fields):
            return EvidenceStatus.UNKNOWN
        digest = item.evidence_sha256
        if type(digest) is not str or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            return EvidenceStatus.UNKNOWN
    if any(getattr(expected, field) != getattr(actual, field) for field in fields):
        return EvidenceStatus.CONFLICT
    if not compare_digest(expected.evidence_sha256, actual.evidence_sha256):
        return EvidenceStatus.CONFLICT
    return EvidenceStatus.MATCH
