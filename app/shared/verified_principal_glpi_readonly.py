"""Per-request OIDC -> signed xref -> independently ACL'd Core/GLPI GETs.

The returned callable accepts only a bearer and ticket ID. Actor/tenant are
derived by the OIDC/JTI + PostgreSQL grant resolver; upstream credentials,
event fetch, ACL decisions and origins are server-injected. GET-only; no
Copilot query, HITL proposal, Core/GLPI write, or execution.
"""
from collections.abc import Callable

from shared.glpi_http_json_transport import make_json_get
from shared.glpi_session_readonly import make_glpi_session_ticket_get
from shared.glpi_http_readers import make_core_glpi_readers
from shared.glpi_readback_comparison import compare_raw_readbacks_to_association
from shared.glpi_native_ticket_acl import make_glpi_native_ticket_acl
from shared.verified_principal_glpi_xref import (
    make_verified_principal_glpi_xref_resolver,
)


class VerifiedGLPIReadbackBlocked(PermissionError):
    """The verified principal could not complete both independently authorized reads."""


def make_verified_principal_glpi_readonly_qualifier(
    *,
    connect: Callable,
    secret: bytes,
    fetch_signed_event: Callable,
    authorize_core_read: Callable,
    authorize_glpi_read: Callable,
    core_token: Callable,
    glpi_app_token: Callable,
    glpi_user_token: Callable,
    core_base_url: str,
    glpi_base_url: str,
    clock: Callable | None = None,
):
    required = (
        connect, fetch_signed_event,
        authorize_core_read, authorize_glpi_read, core_token,
        glpi_app_token, glpi_user_token,
    )
    if not callable(connect) or not all(callable(fn) for fn in required[1:]):
        raise ValueError("verified_glpi_readonly_trust_dependencies_missing")
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("xref_signing_key_missing")

    # These are server-owned transports; they never accept a URL from a request.
    core_get = make_json_get(get_token=core_token, allowed_origin=core_base_url)
    glpi_get = make_glpi_session_ticket_get(
        glpi_base_url=glpi_base_url,
        get_app_token=glpi_app_token,
        get_user_token=glpi_user_token,
    )

    def authorize_read(*, actor, tenant_id, resource, resource_id, **scope):
        if resource == "core_run":
            return authorize_core_read(
                actor=actor, tenant_id=tenant_id, run_id=resource_id
            ) is True
        if resource == "glpi_ticket":
            return authorize_glpi_read(
                actor=actor, tenant_id=tenant_id,
                ticket_id=resource_id,
                glpi_instance_id=scope.get("glpi_instance_id"),
            ) is True
        return False

    read_core_raw, read_glpi_raw = make_core_glpi_readers(
        core_base_url=core_base_url,
        glpi_base_url=glpi_base_url,
        core_get=core_get,
        glpi_get=glpi_get,
        authorize_read=authorize_read,
    )

    authorize_glpi_native_acl = make_glpi_native_ticket_acl(
        glpi_base_url=glpi_base_url,
        get_app_token=glpi_app_token,
        get_actor_user_token=glpi_user_token,
    )

    resolve_ticket = make_verified_principal_glpi_xref_resolver(
        connect=connect,
        secret=secret,
        fetch_signed_event=fetch_signed_event,
        authorize_glpi_native_acl=authorize_glpi_native_acl,
        clock=clock,
    )

    def qualify(*, bearer_token: str, ticket_id: str):
        try:
            # Identity and JTI revocation are re-verified inside this call.
            association = resolve_ticket(bearer_token, ticket_id)
            actor = association["actor"]
            tenant_id = association["tenant_id"]
            run_id = association["run_id"]
            core_payload = read_core_raw(
                actor=actor, tenant_id=tenant_id, run_id=run_id
            )
            glpi_payload = read_glpi_raw(
                actor=actor, tenant_id=tenant_id,
                ticket_id=association["ticket_id"],
                glpi_instance_id=association["glpi_instance_id"],
            )
            comparison = compare_raw_readbacks_to_association(
                association=association,
                core_payload=core_payload,
                glpi_payload=glpi_payload,
            )
            return {
                "status": "OIDC_AUTHENTICATED_READ_ONLY_XREF_MATCH",
                "actor": actor,
                "tenant_id": tenant_id,
                "glpi_instance_id": association["glpi_instance_id"],
                "run_id": comparison["run_id"],
                "incident_id": comparison["incident_id"],
                "ticket_id": comparison["ticket_id"],
                "glpi_entity_id": comparison["glpi_entity_id"],
                "raw_readbacks_match": True,
                "copilot_context_authorized": False,
                "copilot_query_performed": False,
                "hitl_proposal_created": False,
                "glpi_write_performed": False,
                "core_write_performed": False,
                "execution_allowed": False,
            }
        except Exception as exc:
            raise VerifiedGLPIReadbackBlocked(
                "verified_glpi_readonly_readback_not_qualified"
            ) from exc

    return qualify
