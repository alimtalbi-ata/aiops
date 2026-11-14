"""Bind signed GLPI xrefs to a verified OIDC actor and active tenant grants.

This is an unmounted server-side resolver, not an HTTP endpoint. The tenant
candidate comes from active PostgreSQL grants, never the browser. A separate
injected GLPI-native ACL evaluator must affirm the exact actor/entity/ticket
read. All missing or uncertain dependencies deny.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from shared.glpi_xref_postgres_nonce import make_postgres_nonce_consumer
from shared.glpi_xref_resolver_factory import make_hmac_canonical_xref_resolver
from shared.oidc_jti_store import make_oidc_jti_store
from shared.verified_principal import principal_from_bearer


_TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}\Z")
_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z")


class VerifiedGLPIXrefDenied(PermissionError):
    """No unique signed xref is authorized for this verified principal."""


def make_verified_principal_glpi_xref_resolver(
    *,
    connect: Callable,
    bearer_token: str,
    secret: bytes,
    fetch_signed_event: Callable,
    authorize_glpi_native_acl: Callable,
    clock: Callable | None = None,
):
    """Return resolve_ticket(ticket_id), with actor/tenant derived server-side.

    OIDC principal and JTI revocation are checked at construction. Candidate
    tenants are loaded from active actor grants. For each candidate, the signed
    event must bind actor+tenant+ticket, pass durable nonce replay protection,
    and pass an injected native GLPI ACL check. Exactly one candidate may pass.
    The native ACL callback signature is:
      (actor, tenant_id, glpi_instance_id, glpi_entity_id, ticket_id, action)
    It must return exactly True for action="read_ticket".
    """
    if not callable(connect):
        raise ValueError("postgres_connection_factory_missing")
    if not callable(fetch_signed_event) or not callable(authorize_glpi_native_acl):
        raise ValueError("glpi_server_acl_dependencies_missing")
    if clock is not None and not callable(clock):
        raise ValueError("clock_invalid")

    is_revoked, _, _ = make_oidc_jti_store(connect)
    principal = principal_from_bearer(bearer_token, is_revoked=is_revoked)
    actor = principal.actor_id
    consume_nonce = make_postgres_nonce_consumer(connect)

    def active_tenants():
        connection = connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_id FROM aiops.portal_actor_tenant_grants "
                        "WHERE actor_id = %s AND revoked_at IS NULL ORDER BY tenant_id",
                        (actor,),
                    )
                    rows = cursor.fetchall()
            values = []
            for row in rows:
                if (not isinstance(row, (tuple, list)) or len(row) != 1
                        or not isinstance(row[0], str)
                        or not _TENANT.fullmatch(row[0])):
                    raise VerifiedGLPIXrefDenied("tenant_grants_invalid")
                values.append(row[0])
            if len(values) != len(set(values)):
                raise VerifiedGLPIXrefDenied("tenant_grants_ambiguous")
            return values
        except VerifiedGLPIXrefDenied:
            raise
        except Exception as exc:
            raise VerifiedGLPIXrefDenied("tenant_grants_unavailable") from exc
        finally:
            connection.close()

    fatal_acl_error = []

    def authorize_actor(*, actor: str, tenant_id: str, ticket_id: str, claims: dict):
        if actor != principal.actor_id or not _TENANT.fullmatch(tenant_id):
            return False
        if not isinstance(claims, dict):
            return False
        connection = connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM aiops.portal_actor_tenant_grants "
                        "WHERE actor_id = %s AND tenant_id = %s AND revoked_at IS NULL",
                        (principal.actor_id, tenant_id),
                    )
                    membership = cursor.fetchone()
            if membership is None:
                return False
        except Exception as exc:
            fatal_acl_error.append("tenant_membership_unavailable")
            raise exc
        finally:
            connection.close()

        try:
            allowed = authorize_glpi_native_acl(
                actor=principal.actor_id,
                tenant_id=tenant_id,
                glpi_instance_id=claims.get("glpi_instance_id"),
                glpi_entity_id=claims.get("glpi_entity_id"),
                ticket_id=ticket_id,
                action="read_ticket",
            )
        except Exception as exc:
            fatal_acl_error.append("glpi_native_acl_unavailable")
            raise exc
        return allowed is True

    resolver = make_hmac_canonical_xref_resolver(
        secret=secret,
        fetch_signed_event=fetch_signed_event,
        consume_nonce=consume_nonce,
        authorize_actor=authorize_actor,
        clock=clock,
    )

    def resolve_ticket(ticket_id: str):
        if not isinstance(ticket_id, str) or not _TICKET.fullmatch(ticket_id):
            raise VerifiedGLPIXrefDenied("invalid_ticket_id")
        matches = []
        for tenant_id in active_tenants():
            try:
                result = resolver(actor=actor, tenant_id=tenant_id, ticket_id=ticket_id)
            except Exception:
                if fatal_acl_error:
                    raise VerifiedGLPIXrefDenied(fatal_acl_error[-1])
                continue
            matches.append(result)
        if len(matches) != 1:
            raise VerifiedGLPIXrefDenied(
                "signed_xref_missing_or_ambiguous" if matches
                else "signed_xref_not_authorized"
            )
        return matches[0]

    return resolve_ticket
