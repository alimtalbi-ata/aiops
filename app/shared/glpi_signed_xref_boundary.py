"""Canonical GLPI xref boundary: verified claims only, never database row alone.

The verifier is a server-installed, audited function that must authenticate a
signed cross-reference event, its issuer, audience, expiry and tenant/actor ACL.
This module cannot implement those checks without a real trust root. It refuses
to resolve anything when no verifier is installed. A plain glpi_ticket_links row
or a client-supplied 'verified' flag is NOT sufficient.
"""
import re
from collections.abc import Callable

_RUN = re.compile(r"RUN-[A-Z0-9]{8,64}\Z")
_INCIDENT = re.compile(r"INC-[A-Za-z0-9_-]{4,128}\Z")
_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z")
_FIELDS = ("tenant_id", "glpi_instance_id", "glpi_entity_id",
           "ticket_id", "incident_id", "run_id")


class CanonicalXrefBlocked(ValueError):
    pass


def resolve_signed_glpi_xref(
    *, actor, tenant_id, ticket_id, fetch_signed_event: Callable | None = None,
    verify_event_and_acl: Callable | None = None,
):
    """Return identity only from a server-verifier's authenticated claims.

    fetch_signed_event must return one unambiguous server-fetched event;
    verify_event_and_acl must return verified *claims* (not a bool), bound to
    the requested actor, tenant and ticket. The verifier must enforce issuer,
    signature, expiration, replay protection and actor/tenant ACL itself.
    """
    if not all(isinstance(v, str) and v and len(v) <= 128
               for v in (actor, tenant_id, ticket_id)):
        raise CanonicalXrefBlocked("invalid_scope")
    if not _TICKET.fullmatch(ticket_id):
        raise CanonicalXrefBlocked("invalid_ticket")
    if not callable(fetch_signed_event) or not callable(verify_event_and_acl):
        raise CanonicalXrefBlocked("signed_xref_verifier_unavailable")
    try:
        event = fetch_signed_event(actor=actor, tenant_id=tenant_id,
                                   ticket_id=ticket_id)
        if not isinstance(event, dict):
            raise ValueError("event_missing")
        claims = verify_event_and_acl(event=event, actor=actor,
                                      tenant_id=tenant_id, ticket_id=ticket_id)
        if not isinstance(claims, dict):
            raise ValueError("verified_claims_missing")
        if (claims.get("actor") != actor or claims.get("tenant_id") != tenant_id
                or claims.get("ticket_id") != ticket_id):
            raise ValueError("verified_scope_mismatch")
        if claims.get("association_state") != "ACTIVE":
            raise ValueError("inactive_xref")
        if type(claims.get("association_count")) is not int or claims["association_count"] != 1:
            raise ValueError("ambiguous_xref")
        if any(not isinstance(claims.get(k), str) or not claims[k]
               for k in _FIELDS):
            raise ValueError("identity_missing")
        if (not _RUN.fullmatch(claims["run_id"])
                or not _INCIDENT.fullmatch(claims["incident_id"])
                or not claims["glpi_entity_id"].isascii()
                or not claims["glpi_entity_id"].isdecimal()):
            raise ValueError("identity_invalid")
        return {key: claims[key] for key in _FIELDS}
    except Exception as exc:
        raise CanonicalXrefBlocked("signed_xref_not_qualified") from exc
