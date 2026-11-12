"""FS147 cross-snapshot identity check. Pure: never authorizes an effect.

Use immediately before transactional revalidation; all snapshots must originate
from authoritative reads. No GLPI/Temporal/DB calls are made here.
"""
from dataclasses import dataclass
from enum import Enum


class Coherence(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    MATCH = "MATCH"


@dataclass(frozen=True)
class LinkIdentity:
    tenant_id: str
    idempotency_key: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    evidence_sha256: str
    glpi_ticket_id: int
    mode: str


def classify_coherence(*snapshots):
    """Never treat missing/ambiguous identities as a successful replay."""
    if len(snapshots) < 2 or any(not isinstance(s, LinkIdentity) for s in snapshots):
        return Coherence.UNKNOWN
    for s in snapshots:
        fields = (s.tenant_id, s.idempotency_key, s.alert_fingerprint,
                  s.incident_id, s.run_id, s.evidence_id, s.evidence_sha256)
        if any(type(v) is not str or not v.strip() for v in fields):
            return Coherence.UNKNOWN
        if type(s.mode) is not str or not s.mode.strip() or type(s.glpi_ticket_id) is not int:
            return Coherence.UNKNOWN
    if any(s.mode != "DEMO" or s.glpi_ticket_id != 147 for s in snapshots):
        return Coherence.DENIED
    if any(len(s.evidence_sha256) != 64 or
           any(c not in "0123456789abcdef" for c in s.evidence_sha256)
           for s in snapshots):
        return Coherence.UNKNOWN
    return Coherence.MATCH if all(s == snapshots[0] for s in snapshots[1:]) else Coherence.DENIED
