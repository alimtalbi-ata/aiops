import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_actor_credential_broker import (
    GLPIActorCredentialDenied, make_glpi_actor_user_token_broker,
)

ACTOR = "oidc:" + "a" * 64
ARGS = dict(actor=ACTOR, tenant_id="tenant-a", ticket_id="42",
            glpi_instance_id="glpi-eu")


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params): self.executed.append((sql, params))
    def fetchall(self): return self.rows


class Connection:
    def __init__(self, rows):
        self.cursor_obj = Cursor(rows)
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return self.cursor_obj
    def close(self): self.closed = True


def test_actor_broker_requires_active_grant_verified_binding_and_vault_identity():
    conn = Connection([(17,)])
    seen = []
    def vault(**scope):
        seen.append(scope)
        return dict(glpi_user_id=17, glpi_instance_id="glpi-eu",
                    tenant_id="tenant-a", user_token="user-specific-secret")
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: conn, get_bound_credential=vault)
    assert broker(**ARGS) == "user-specific-secret"
    assert conn.closed
    sql, params = conn.cursor_obj.executed[0]
    assert "glpi_actor_user_bindings" in sql
    assert "portal_actor_tenant_grants" in sql
    assert "b.revoked_at IS NULL" in sql
    assert "g.revoked_at IS NULL" in sql
    assert params == (ACTOR, "tenant-a", "glpi-eu")
    assert seen == [dict(actor=ACTOR, tenant_id="tenant-a",
                         glpi_instance_id="glpi-eu", glpi_user_id=17)]


@pytest.mark.parametrize("rows", [[], [(17,), (18,)], [(True,)], [(0,)],
                                   [("17",)], [(17, 18)]])
def test_missing_ambiguous_or_invalid_binding_denies_without_vault(rows):
    vault = Mock()
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: Connection(rows), get_bound_credential=vault)
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**ARGS)
    vault.assert_not_called()


@pytest.mark.parametrize("credential", [
    "shared-service-token",
    {"user_token": "shared-service-token"},
    dict(glpi_user_id=18, glpi_instance_id="glpi-eu",
         tenant_id="tenant-a", user_token="token"),
    dict(glpi_user_id=17, glpi_instance_id="other",
         tenant_id="tenant-a", user_token="token"),
    dict(glpi_user_id=17, glpi_instance_id="glpi-eu",
         tenant_id="tenant-b", user_token="token"),
    dict(glpi_user_id=17, glpi_instance_id="glpi-eu",
         tenant_id="tenant-a", user_token="bad\\token"),
])
def test_vault_must_attest_exact_glpi_user_instance_and_tenant(credential):
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: Connection([(17,)]),
        get_bound_credential=lambda **_: credential)
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**ARGS)


def test_invalid_scope_denies_before_database_or_vault():
    connect = Mock()
    vault = Mock()
    broker = make_glpi_actor_user_token_broker(
        connect=connect, get_bound_credential=vault)
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**{**ARGS, "ticket_id": "../42"})
    connect.assert_not_called()
    vault.assert_not_called()


def test_database_and_vault_failures_deny():
    def broken_db():
        raise RuntimeError("database offline")
    broker = make_glpi_actor_user_token_broker(
        connect=broken_db, get_bound_credential=lambda **_: None)
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**ARGS)

    broker = make_glpi_actor_user_token_broker(
        connect=lambda: Connection([(17,)]),
        get_bound_credential=lambda **_: (_ for _ in ()).throw(
            RuntimeError("vault offline")))
    with pytest.raises(GLPIActorCredentialDenied):
        broker(**ARGS)
