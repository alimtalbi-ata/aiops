"""Isolated full broker -> GLPI session identity -> native Ticket ACL contract.

Uses the real broker, session transport and native ACL; only PostgreSQL,
the trusted vault and the HTTPS GLPI endpoint are simulated.
"""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_actor_credential_broker import make_glpi_actor_user_token_broker
from shared.glpi_native_ticket_acl import make_glpi_native_ticket_acl


class Cursor:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params):
        assert "glpi_actor_user_bindings" in sql
        assert params == ("oidc:verified-actor", "tenant-a", "glpi-a")
    def fetchall(self): return self.rows


class DB:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return Cursor(self.rows)
    def close(self): pass


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, payload): self.data = io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.data.read(n)


class GLPI:
    def __init__(self, glpi_id, entity=7, ticket_visible=True):
        self.glpi_id = glpi_id
        self.entity = entity
        self.ticket_visible = ticket_visible
        self.calls = []
    def open(self, request, timeout):
        path = request.full_url.split("/apirest.php/")[-1]
        self.calls.append(path)
        if path == "initSession":
            assert request.get_header("Authorization") == "user_token user-17-secret"
            return Response({"session_token": "isolated-session"})
        assert request.get_header("Session-token") == "isolated-session"
        if path == "getFullSession":
            return Response({"session": {"glpiID": self.glpi_id}})
        if path == "Ticket/42":
            if not self.ticket_visible:
                raise PermissionError("GLPI denies this actor")
            return Response({"id": 42, "entities_id": self.entity})
        if path == "killSession": return Response({})
        raise AssertionError(path)


def chain(*, db_rows=None, vault_user=17, session_user=17,
          entity=7, ticket_visible=True):
    glpi = GLPI(session_user, entity=entity, ticket_visible=ticket_visible)
    db_rows = [(17,)] if db_rows is None else db_rows
    broker = make_glpi_actor_user_token_broker(
        connect=lambda: DB(db_rows),
        get_bound_credential=lambda **scope: dict(
            glpi_user_id=vault_user, glpi_instance_id=scope["glpi_instance_id"],
            tenant_id=scope["tenant_id"], user_token="user-17-secret",
        ),
    )
    with patch("shared.glpi_session_readonly.build_opener", return_value=glpi):
        acl = make_glpi_native_ticket_acl(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "isolated-app-token",
            get_actor_user_token=broker,
        )
    return acl, glpi


SCOPE = dict(actor="oidc:verified-actor", tenant_id="tenant-a",
             glpi_instance_id="glpi-a", glpi_entity_id="7",
             ticket_id="42", action="read_ticket")


def test_real_broker_to_native_acl_full_success_chain():
    acl, glpi = chain()
    assert acl(**SCOPE) is True
    assert glpi.calls == ["initSession", "getFullSession", "Ticket/42", "killSession"]


@pytest.mark.parametrize("variant", [
    {"vault_user": 18},
    {"session_user": 18},
    {"session_user": None},
    {"entity": 8},
    {"ticket_visible": False},
    {"db_rows": []},
])
def test_full_chain_denies_wrong_vault_identity_session_entity_or_ticket_acl(variant):
    acl, glpi = chain(**variant)
    assert acl(**SCOPE) is False
    if "session_user" in variant:
        assert "Ticket/42" not in glpi.calls
        assert glpi.calls[-1] == "killSession"
    if "vault_user" in variant or "db_rows" in variant:
        assert glpi.calls == []


def test_full_chain_never_allows_write_action():
    acl, glpi = chain()
    assert acl(**{**SCOPE, "action": "update_ticket"}) is False
    assert glpi.calls == []
