"""Read-only ITSM reconciliation: missing Core xref never implies missing ticket."""
from dataclasses import dataclass
from enum import Enum

class Status(str, Enum):
    MATCHED="MATCHED"
    EXISTING_UNLINKED="EXISTING_UNLINKED"
    AMBIGUOUS="AMBIGUOUS"
    MISSING="MISSING"
    NOT_ELIGIBLE="NOT_ELIGIBLE"
    UNKNOWN="UNKNOWN"
    CONFLICT="CONFLICT"

@dataclass(frozen=True)
class Candidate:
    system: str
    ticket_id: str
    tenant_id: str
    incident_id: str
    run_id: str
    readback_verified: bool

@dataclass(frozen=True)
class Snapshot:
    tenant_id: str
    incident_id: str
    run_id: str
    mode: str
    eligible: bool
    inventory_complete: bool
    xref_ticket_id: str | None
    candidates: tuple[Candidate, ...]

def classify(snapshot: object) -> Status:
    """Pure classification; no POST, xref repair, Temporal signal, or authorization."""
    if not isinstance(snapshot, Snapshot):
        return Status.UNKNOWN
    s = snapshot
    if s.mode == "LIVE" or s.eligible is False:
        return Status.NOT_ELIGIBLE
    if s.mode != "DEMO" or type(s.eligible) is not bool:
        return Status.UNKNOWN
    if any(type(v) is not str or not v or v.strip() != v
           for v in (s.tenant_id, s.incident_id, s.run_id)):
        return Status.UNKNOWN
    if type(s.inventory_complete) is not bool or type(s.candidates) is not tuple:
        return Status.UNKNOWN
    if s.xref_ticket_id is not None and (type(s.xref_ticket_id) is not str or not s.xref_ticket_id):
        return Status.UNKNOWN
    if any(not isinstance(c, Candidate) for c in s.candidates):
        return Status.UNKNOWN
    if any(type(c.readback_verified) is not bool or not c.readback_verified or
           any(type(v) is not str or not v for v in
               (c.system, c.ticket_id, c.tenant_id, c.incident_id, c.run_id))
           for c in s.candidates):
        return Status.UNKNOWN
    exact = [c for c in s.candidates if c.system == "GLPI" and
             (c.tenant_id, c.incident_id, c.run_id) ==
             (s.tenant_id, s.incident_id, s.run_id)]
    if any(c.system == "GLPI" and c.ticket_id == s.xref_ticket_id and
           c not in exact for c in s.candidates):
        return Status.CONFLICT
    ids = {c.ticket_id for c in exact}
    if len(ids) > 1:
        return Status.AMBIGUOUS
    if s.xref_ticket_id is not None:
        if ids and s.xref_ticket_id not in ids:
            return Status.CONFLICT
        return Status.MATCHED if ids else Status.UNKNOWN
    if ids:
        return Status.EXISTING_UNLINKED
    return Status.MISSING if s.inventory_complete else Status.UNKNOWN
