"""FS147 canonical signal identity: pure, fail-closed, no side effects.

A digest is a correlation key, never proof of authorization or delivery.
Canonical length-prefixed encoding avoids delimiter and JSON ambiguity.
"""
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256


class KeyStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"
    VALID = "VALID"


@dataclass(frozen=True)
class SignalIdentity:
    tenant_id: str
    idempotency_key: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    evidence_sha256: str
    workflow_id: str
    action_id: str
    approval_id: str
    fence_token: int
    ticket_id: int
    mode: str


_FIELDS = (
    "tenant_id", "idempotency_key", "alert_fingerprint", "incident_id",
    "run_id", "evidence_id", "evidence_sha256", "workflow_id",
    "action_id", "approval_id",
)


def classify_signal_key(identity):
    """Return (status, digest_or_None). VALID is NOT execution permission."""
    if not isinstance(identity, SignalIdentity):
        return KeyStatus.UNKNOWN, None
    if identity.mode == "LIVE" or type(identity.ticket_id) is int and identity.ticket_id != 147:
        return KeyStatus.DENIED, None
    if identity.mode != "DEMO" or type(identity.ticket_id) is not int:
        return KeyStatus.UNKNOWN, None
    if type(identity.fence_token) is not int or identity.fence_token <= 0:
        return KeyStatus.UNKNOWN, None
    values = [getattr(identity, field) for field in _FIELDS]
    if any(type(value) is not str or not value or value.strip() != value or
           any(ord(ch) < 32 or ord(ch) == 127 for ch in value) or len(value) > 512
           for value in values):
        return KeyStatus.UNKNOWN, None
    digest = identity.evidence_sha256
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        return KeyStatus.UNKNOWN, None
    values += [str(identity.fence_token), str(identity.ticket_id), identity.mode]
    framed = b"FS147-SIGNAL-V1\x00" + b"".join(
        len(value.encode("utf-8")).to_bytes(4, "big") + value.encode("utf-8")
        for value in values
    )
    return KeyStatus.VALID, sha256(framed).hexdigest()
