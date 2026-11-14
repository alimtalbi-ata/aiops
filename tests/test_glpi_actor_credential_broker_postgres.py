"""Disposable PostgreSQL contract for actor->GLPI identity binding (no real tokens)."""
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_actor_credential_broker import (
    GLPIActorCredentialDenied, make_glpi_actor_user_token_broker,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("AIOPS_GLPI_BROKER_REAL_PG_CI") != "1",
    reason="requires explicitly enabled disposable PostgreSQL",
)


def test_revocation_and_tenant_isolation_in_real_postgres():
    import psycopg
    dsn = os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as conn:
        conn.execute((Path("db/migrations") /
                      "009_portal_tenant_actor_read_groundwork.sql").read_text())
        conn.execute((Path("db/migrations") /
                      "012_glpi_actor_credential_bindings.sql").read_text())
    actor = "oidc:" + uuid4().hex
    tenant = "ci-" + uuid4().hex
    other_tenant = "ci-" + uuid4().hex
    instance = "ci-glpi"
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO aiops.portal_actor_tenant_grants (actor_id, tenant_id) "
            "VALUES (%s, %s)", (actor, tenant),
        )
        conn.execute(
            "INSERT INTO aiops.glpi_actor_user_bindings "
            "(actor_id, tenant_id, glpi_instance_id, glpi_user_id, verified_at) "
            "VALUES (%s, %s, %s, %s, now())",
            (actor, tenant, instance, 17),
        )
    # The same active GLPI user cannot be assigned to another OIDC actor
    # within the same tenant and GLPI instance.
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO aiops.glpi_actor_user_bindings "
                "(actor_id, tenant_id, glpi_instance_id, glpi_user_id, verified_at) "
                "VALUES (%s, %s, %s, %s, now())",
                ("oidc:" + uuid4().hex, tenant, instance, 17),
            )
    vault_calls = []
    def vault(**kwargs):
        vault_calls.append(kwargs)
        return dict(glpi_user_id=17, glpi_instance_id=instance,
                    tenant_id=tenant, user_token="ci-only-actor-token")
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: psycopg.connect(dsn), get_bound_credential=vault)
    scope = dict(actor=actor, tenant_id=tenant, glpi_instance_id=instance,
                 ticket_id="42")
    assert broker(**scope) == {"user_token": "ci-only-actor-token", "glpi_user_id": 17}
    assert len(vault_calls) == 1
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**{**scope, "tenant_id": other_tenant})
    assert len(vault_calls) == 1

    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE aiops.portal_actor_tenant_grants SET revoked_at = now() "
            "WHERE actor_id = %s AND tenant_id = %s", (actor, tenant),
        )
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**scope)
    assert len(vault_calls) == 1

    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE aiops.portal_actor_tenant_grants SET revoked_at = NULL "
            "WHERE actor_id = %s AND tenant_id = %s", (actor, tenant),
        )
        conn.execute(
            "UPDATE aiops.glpi_actor_user_bindings SET revoked_at = now() "
            "WHERE actor_id = %s AND tenant_id = %s AND glpi_instance_id = %s",
            (actor, tenant, instance),
        )
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**scope)
    assert len(vault_calls) == 1


def test_real_postgres_revocation_during_vault_lookup_denies():
    import psycopg
    dsn = os.environ["DATABASE_URL"]
    actor = "oidc:" + uuid4().hex
    tenant = "ci-" + uuid4().hex
    instance = "ci-glpi"
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO aiops.portal_actor_tenant_grants (actor_id, tenant_id) "
            "VALUES (%s, %s)", (actor, tenant),
        )
        conn.execute(
            "INSERT INTO aiops.glpi_actor_user_bindings "
            "(actor_id, tenant_id, glpi_instance_id, glpi_user_id, verified_at) "
            "VALUES (%s, %s, %s, %s, now())",
            (actor, tenant, instance, 19),
        )
    def vault(**_):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE aiops.portal_actor_tenant_grants SET revoked_at = now() "
                "WHERE actor_id = %s AND tenant_id = %s", (actor, tenant),
            )
        return dict(glpi_user_id=19, glpi_instance_id=instance,
                    tenant_id=tenant, user_token="ci-only-secret")
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: psycopg.connect(dsn), get_bound_credential=vault)
    with pytest.raises(GLPIActorCredentialDenied, match="glpi_actor_binding_changed"):
        broker(actor=actor, tenant_id=tenant, ticket_id="42",
               glpi_instance_id=instance)
