"""FS364 GLPI 147 read boundary. No write, launch, approval or host access.

Only a trusted backend may inject these adapters. Never infer ownership from GLPI
free text or from caller-provided booleans. Network/ACL errors fail closed.
"""
from collections.abc import Mapping
from .fs364_ticket_verification import Ticket147Snapshot, ticket147_matches


def verify_ticket147_readonly(link, *, tenant_id, actor_id, glpi_get,
                              authoritative_owner, authorize_actor):
    """Return False unless three independent backend reads agree.

    glpi_get(147) must use backend credentials and return parsed GET /Ticket/147.
    authoritative_owner(147) returns a trusted (tenant_id, incident_id) pair.
    authorize_actor(actor_id, tenant_id, 147) performs server-side ACL lookup.
    Callers must not bind/launch on False.
    """
    if (not isinstance(tenant_id, str) or not tenant_id.strip()
            or tenant_id != tenant_id.strip()
            or not isinstance(actor_id, str) or not actor_id.strip()
            or actor_id != actor_id.strip()):
        return False
    try:
        # Deny before reading ticket or ownership data. Only literal True grants access.
        acl = authorize_actor(actor_id, tenant_id, 147)
        if acl is not True:
            return False
        # No client supplied ticket id; never create a duplicate ticket.
        ticket = glpi_get(147)
        # GLPI deletion state must be explicit and false; absent/ambiguous is not safe.
        if (not isinstance(ticket, Mapping)
                or type(ticket.get("is_deleted")) is not int
                or ticket["is_deleted"] != 0):
            return False
        # Reject a wrong or malformed GLPI identity before consulting ownership.
        if (type(ticket.get("id")) is not int or ticket["id"] != 147
                or type(ticket.get("type")) is not int or ticket["type"] != 1
                or ticket.get("name") != "AIOPS2-REAL-FS-20261106"):
            return False
        owner = authoritative_owner(147)
        if not isinstance(ticket, Mapping) or not isinstance(owner, tuple) or len(owner) != 2:
            return False
        if owner != (tenant_id, link.incident_id):
            return False
        # GLPI's entities_id is NOT a tenant ownership proof; owner is external.
        snapshot = Ticket147Snapshot(
            ticket_id=ticket.get("id"),
            ticket_type=ticket.get("type"),
            reference=ticket.get("name"),
            tenant_id=owner[0],
            incident_id=owner[1],
            fetched_from_glpi=True,
        )
        return ticket147_matches(link, snapshot, expected_tenant_id=tenant_id,
                                 authenticated=True, acl_ok=acl)
    except (Exception):
        # Authentication, transport, parse, ACL and owner-store errors all block.
        return False
