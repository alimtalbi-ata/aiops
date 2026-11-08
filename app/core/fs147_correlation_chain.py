"""FS147 immutable correlation snapshot guard. No I/O, no side effects."""
from dataclasses import dataclass
from enum import Enum
import unicodedata


class CorrelationDecision(str, Enum):
    MATCH = "MATCH"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


@dataclass(frozen=True)
class CorrelationLink:
    tenant_id: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    ticket_id: int
    mode: str


def _valid_identifier(value):
    return (
        type(value) is str and 0 < len(value) <= 512
        and value == value.strip()
        and all(
            unicodedata.category(ch) not in ("Cc", "Cf", "Cs")
            for ch in value
        )
    )


def classify_correlation(expected, observed):
    """Compare authenticated snapshots; MATCH is not launch authorization.

    Caller must independently prove both snapshots were read from durable,
    authenticated sources in one consistent transactional view. Missing or
    malformed data cannot be promoted to MATCH.
    """
    if not isinstance(expected, CorrelationLink) or not isinstance(observed, CorrelationLink):
        return CorrelationDecision.UNKNOWN
    if expected.mode == "LIVE" or observed.mode == "LIVE":
        return CorrelationDecision.DENIED
    if (type(expected.ticket_id) is int and expected.ticket_id != 147) or (
        type(observed.ticket_id) is int and observed.ticket_id != 147
    ):
        return CorrelationDecision.DENIED
    if expected.mode != "DEMO" or observed.mode != "DEMO":
        return CorrelationDecision.UNKNOWN
    if type(expected.ticket_id) is not int or type(observed.ticket_id) is not int:
        return CorrelationDecision.UNKNOWN
    names = ("tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id")
    if any(not _valid_identifier(getattr(link, name)) for link in (expected, observed) for name in names):
        return CorrelationDecision.UNKNOWN
    if any(getattr(expected, name) != getattr(observed, name) for name in names):
        return CorrelationDecision.CONFLICT
    return CorrelationDecision.MATCH
