"""Fail-closed server-owned broker for per-actor GLPI user credentials.

OIDC principal is resolved before this callback is invoked. PostgreSQL holds
only an explicit reviewed identity binding, never tokens. A separate trusted
vault must return a credential *attested* for that GLPI user, instance and
tenant. No shared service-user fallback, no auto-provisioning, no write API.
"""
from collections.abc import Callable
import re


class GLPIActorCredentialDenied(PermissionError):
    """No unambiguous verified actor-to-GLPI-user credential is available."""


def make_glpi_actor_user_token_broker(*, connect: Callable,
                                      get_bound_credential: Callable):
    if not callable(connect) or not callable(get_bound_credential):
        raise ValueError("glpi_actor_credential_broker_dependencies_missing")

    def valid(value, limit):
        return (isinstance(value, str) and bool(value.strip())
                and len(value) <= limit
                and not any(ord(ch) < 33 or ord(ch) > 126 for ch in value))

    def get_user_token(*, actor, tenant_id, ticket_id, glpi_instance_id):
        if (not valid(actor, 200) or not valid(tenant_id, 128)
                or not valid(glpi_instance_id, 128)
                or not isinstance(ticket_id, str)
                or re.fullmatch(r"[1-9][0-9]{0,17}", ticket_id) is None):
            raise GLPIActorCredentialDenied("glpi_actor_scope_invalid")

        try:
            connection = connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT b.glpi_user_id "
                            "FROM aiops.glpi_actor_user_bindings b "
                            "JOIN aiops.portal_actor_tenant_grants g "
                            "ON g.actor_id = b.actor_id AND g.tenant_id = b.tenant_id "
                            "WHERE b.actor_id = %s AND b.tenant_id = %s "
                            "AND b.glpi_instance_id = %s "
                            "AND b.revoked_at IS NULL AND b.verified_at <= now() "
                            "AND g.revoked_at IS NULL",
                            (actor, tenant_id, glpi_instance_id),
                        )
                        rows = cursor.fetchall()
            finally:
                connection.close()
            if (not isinstance(rows, (list, tuple)) or len(rows) != 1
                    or not isinstance(rows[0], (tuple, list))
                    or len(rows[0]) != 1 or type(rows[0][0]) is not int
                    or rows[0][0] <= 0):
                raise GLPIActorCredentialDenied("glpi_actor_binding_missing_or_ambiguous")
            user_id = rows[0][0]
            credential = get_bound_credential(
                actor=actor, tenant_id=tenant_id,
                glpi_instance_id=glpi_instance_id, glpi_user_id=user_id,
            )
            # The vault must attest the exact GLPI account, not merely return
            # a token string. This is still a trusted server dependency.
            if (not isinstance(credential, dict)
                    or set(credential) != {"glpi_user_id", "glpi_instance_id",
                                           "tenant_id", "user_token"}
                    or type(credential["glpi_user_id"]) is not int
                    or credential["glpi_user_id"] != user_id
                    or credential["glpi_instance_id"] != glpi_instance_id
                    or credential["tenant_id"] != tenant_id
                    or not valid(credential["user_token"], 4096)):
                raise GLPIActorCredentialDenied("glpi_vault_identity_not_attested")
            return credential["user_token"]
        except GLPIActorCredentialDenied:
            raise
        except Exception as exc:
            raise GLPIActorCredentialDenied("glpi_actor_credentials_unavailable") from exc

    return get_user_token
