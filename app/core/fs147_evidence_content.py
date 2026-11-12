"""FS147 read-only evidence content verification; no side effects.

A stored digest is a claim, not proof that the fetched bytes match it.
Only a complete, authenticated and durable read can establish MATCH.
"""
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from hmac import compare_digest

from app.core.fs147_evidence_provenance import (
    EvidenceBinding, EvidenceObservation, EvidenceStatus, classify_evidence_binding,
)


class ContentStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"
    CONFLICT = "CONFLICT"
    MATCH = "MATCH"


@dataclass(frozen=True)
class EvidenceContentRead:
    observation: EvidenceObservation
    content: bytes
    complete: bool
    authenticated: bool


def classify_evidence_content(expected: EvidenceBinding, read: EvidenceContentRead | None) -> ContentStatus:
    """MATCH is content integrity only; never authorizes Policy/HITL/Temporal."""
    if not isinstance(expected, EvidenceBinding):
        return ContentStatus.UNKNOWN
    if expected.mode == "LIVE" or (type(expected.ticket_id) is int and expected.ticket_id != 147):
        return ContentStatus.DENIED
    if not isinstance(read, EvidenceContentRead):
        return ContentStatus.UNKNOWN
    status = classify_evidence_binding(expected, read.observation)
    if status == EvidenceStatus.DENIED:
        return ContentStatus.DENIED
    if status == EvidenceStatus.CONFLICT:
        return ContentStatus.CONFLICT
    if status != EvidenceStatus.MATCH:
        return ContentStatus.UNKNOWN
    if type(read.complete) is not bool or type(read.authenticated) is not bool:
        return ContentStatus.UNKNOWN
    if not read.complete or not read.authenticated or type(read.content) is not bytes:
        return ContentStatus.UNKNOWN
    if not compare_digest(sha256(read.content).hexdigest(), expected.evidence_sha256):
        return ContentStatus.CONFLICT
    return ContentStatus.MATCH
