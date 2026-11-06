"""Read-only backend GLPI 147 identity boundary. No ticket writes or Temporal actions."""
from collections.abc import Mapping
from dataclasses import dataclass

class VerificationDenied(Exception):
    pass

@dataclass(frozen=True)
class TicketIdentity:
    ticket_id: int
    tenant_id: str
    incident_ref: str

def verify_ticket147(*, get_ticket, authorize, tenant_id, actor_id, incident_ref):
    """Adapters must be backend-owned: authenticated GLPI GET and server-side ACL.

    The ticket mapping is an explicitly normalized adapter response, not raw
    untrusted frontend JSON or an assumption about native GLPI custom fields.
    """
    if not all(isinstance(x, str) and x.strip() and x == x.strip()
               for x in (tenant_id, actor_id, incident_ref)):
        raise VerificationDenied("invalid identity")
    try:
        permitted = authorize(tenant_id, actor_id, 147)
    except Exception as exc:
        raise VerificationDenied("ACL unavailable") from exc
    if permitted is not True:
        raise VerificationDenied("ACL denied")
    try:
        ticket = get_ticket(147)
    except Exception as exc:
        raise VerificationDenied("GLPI unavailable") from exc
    if not isinstance(ticket, Mapping):
        raise VerificationDenied("invalid GLPI response")
    if type(ticket.get("id")) is not int or ticket["id"] != 147:
        raise VerificationDenied("wrong ticket")
    if (type(ticket.get("type")) is not int or ticket["type"] != 1
            or ticket.get("name") != "AIOPS2-REAL-FS-20261106"):
        raise VerificationDenied("wrong incident ticket identity")
    if ticket.get("tenant_id") != tenant_id or ticket.get("incident_ref") != incident_ref:
        raise VerificationDenied("ticket ownership mismatch")
    if type(ticket.get("is_deleted")) is not int or ticket["is_deleted"] != 0:
        raise VerificationDenied("ticket deleted or deletion state unknown")
    return TicketIdentity(147, tenant_id, incident_ref)
