"""FS147 deterministic correlation idempotency identity (pure, no I/O).

The digest identifies a *requested binding*, not proof of durable uniqueness,
authentication, GLPI state, or permission to launch a run.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import unicodedata


class KeyStatus(str, Enum):
    READY = "READY"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


@dataclass(frozen=True)
class KeyResult:
    status: KeyStatus
    key: str | None = None


def _identifier(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 512
        and value == value.strip()
        and unicodedata.is_normalized("NFC", value)
        and all(unicodedata.category(ch) not in ("Cc", "Cf", "Cs") for ch in value)
    )


def derive_fs147_key(*, tenant_id: object, alert_fingerprint: object,
                     incident_id: object, run_id: object, evidence_id: object,
                     ticket_id: object, mode: object) -> KeyResult:
    """Derive stable versioned digest only for complete DEMO ticket-147 binding.

    The caller MUST enforce a DB unique constraint and compare the persisted
    binding under a transaction. A key collision or same-key divergent payload
    is CONFLICT at persistence, never a reason to create another GLPI ticket.
    """
    if mode == "LIVE" or (type(ticket_id) is int and ticket_id != 147):
        return KeyResult(KeyStatus.DENIED)
    if mode != "DEMO" or type(ticket_id) is not int:
        return KeyResult(KeyStatus.UNKNOWN)
    fields = (tenant_id, alert_fingerprint, incident_id, run_id, evidence_id)
    if not all(_identifier(v) for v in fields):
        return KeyResult(KeyStatus.UNKNOWN)
    payload = json.dumps(
        ["fs147-binding-v1", *fields, ticket_id, mode],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")
    return KeyResult(KeyStatus.READY, "fs147:v1:" + hashlib.sha256(payload).hexdigest())
