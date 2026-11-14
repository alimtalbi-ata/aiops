"""Enforce GLPI's own per-user ticket-read permission before xref acceptance.

The user-token provider MUST return a credential for this exact OIDC-derived
actor, tenant and GLPI instance; shared service-user fallback is forbidden.
GLPI's authenticated Ticket GET is the authorization decision. The returned
entity ID is compared with the signed xref claim. No write endpoints exist.
"""
from collections.abc import Callable
import re

from shared.glpi_session_readonly import make_glpi_session_ticket_get


class GLPINativeTicketACLBlocked(PermissionError):
    """GLPI did not authorize the actor to read the exact ticket/entity."""


def make_glpi_native_ticket_acl(
    *,
    glpi_base_url: str,
    get_app_token: Callable,
    get_actor_user_token: Callable,
):
    if not callable(get_app_token) or not callable(get_actor_user_token):
        raise ValueError("actor_bound_glpi_credentials_required")

    # This session reader invokes the actor-bound token provider with actor,
    # tenant, ticket and instance on every authorization check. GLPI itself
    # enforces the user's Ticket read right on the GET.
    read_as_actor = make_glpi_session_ticket_get(
        glpi_base_url=glpi_base_url,
        get_app_token=get_app_token,
        get_user_token=get_actor_user_token,
    )

    def authorize(*, actor, tenant_id, glpi_instance_id,
                  glpi_entity_id, ticket_id, action):
        if action != "read_ticket":
            return False
        if (not isinstance(actor, str) or not actor.strip()
                or not isinstance(tenant_id, str) or not tenant_id.strip()
                or not isinstance(glpi_instance_id, str) or not glpi_instance_id.strip()
                or not isinstance(ticket_id, str)
                or not re.fullmatch(r"[1-9][0-9]{0,17}", ticket_id)
                or not isinstance(glpi_entity_id, str)
                or not re.fullmatch(r"(?:0|[1-9][0-9]{0,17})", glpi_entity_id)):
            return False
        try:
            ticket = read_as_actor(
                url=glpi_base_url.rstrip("/") + "/Ticket/" + ticket_id,
                actor=actor,
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                glpi_instance_id=glpi_instance_id,
            )
            observed_id = ticket.get("id")
            observed_entity = ticket.get("entities_id")
            return (
                type(observed_id) in (str, int)
                and str(observed_id) == ticket_id
                and type(observed_entity) in (str, int)
                and str(observed_entity) == glpi_entity_id
            )
        except Exception:
            # Upstream denial, timeout, invalid response or failed cleanup deny.
            return False

    return authorize
