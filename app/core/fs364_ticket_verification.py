"""FS364 backend GLPI 147 ownership gate; read-only and fail-closed.

Caller MUST fetch the ticket with an authenticated backend GLPI client.
incident_id must be an authoritative backend mapping, never free-text GLPI data.
This check does not authorize launch, resume, approval, or LIVE effects.
"""
from dataclasses import dataclass
from .fs364_correlation import Link, validate


@dataclass(frozen=True)
class Ticket147Snapshot:
    ticket_id: int
    ticket_type: int
    reference: str
    tenant_id: str
    incident_id: str
    fetched_from_glpi: bool


def ticket147_matches(link: Link, ticket: Ticket147Snapshot, *,
                      expected_tenant_id: str, authenticated: bool,
                      acl_ok: bool) -> bool:
    """Verify identity and ownership before binding; never creates a ticket."""
    try:
        validate(link)
        return (authenticated is True and acl_ok is True
                and ticket.fetched_from_glpi is True
                and type(ticket.ticket_id) is int and ticket.ticket_id == 147
                and type(ticket.ticket_type) is int and ticket.ticket_type == 1
                and ticket.reference == "AIOPS2-REAL-FS-20261106"
                and isinstance(expected_tenant_id, str)
                and bool(expected_tenant_id.strip())
                and expected_tenant_id == expected_tenant_id.strip()
                and ticket.tenant_id == expected_tenant_id
                and ticket.incident_id == link.incident_id)
    except (ValueError, TypeError, AttributeError):
        return False
