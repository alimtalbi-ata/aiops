"""FS147 immutable correlation admission; pure, no GLPI/Temporal side effects."""
from dataclasses import dataclass
from enum import Enum
import re


class LinkDecision(str, Enum):
    NEW = "NEW"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


@dataclass(frozen=True)
class Link:
    tenant_id: str
    idempotency_key: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    evidence_sha256: str
    glpi_ticket_id: int
    mode: str


_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _valid(x):
    return (isinstance(x, Link)
            and all(type(getattr(x, field)) is str
                    and _TOKEN.fullmatch(getattr(x, field))
                    for field in ("tenant_id", "idempotency_key",
                                  "alert_fingerprint", "incident_id",
                                  "run_id", "evidence_id"))
            and type(x.evidence_sha256) is str
            and bool(_DIGEST.fullmatch(x.evidence_sha256))
            and type(x.glpi_ticket_id) is int
            and type(x.mode) is str)


def classify_link(candidate, existing=None):
    """Classify immutable identity; NEW is not permission to persist or launch.

    Caller must enforce UNIQUE(tenant_id, idempotency_key) transactionally.
    An existing row is authoritative only when read from the same tenant scope.
    """
    if not _valid(candidate):
        return LinkDecision.UNKNOWN
    if candidate.mode != "DEMO" or candidate.glpi_ticket_id != 147:
        return LinkDecision.DENIED
    if existing is None:
        return LinkDecision.NEW
    if not _valid(existing):
        return LinkDecision.UNKNOWN
    if existing.mode != "DEMO" or existing.glpi_ticket_id != 147:
        return LinkDecision.CONFLICT
    if (candidate.tenant_id, candidate.idempotency_key) != (
            existing.tenant_id, existing.idempotency_key):
        return LinkDecision.CONFLICT
    return LinkDecision.REPLAY if candidate == existing else LinkDecision.CONFLICT
