"""Core exact-Run SQL contract: server identity and tenant grants at source."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from core.portal_tenant_runs import (
    EXACT_RUN_FOR_ACTOR_SQL, RUN_FIELDS, read_exact_run_for_verified_actor,
)


class Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.row


def test_core_exact_run_authorized_and_unbound_runs_invisible():
    row = ("RUN-A", "INC-A", "DEMO", "scenario-a", "DONE", 1, 0.8,
           None, None, None)
    cursor = Cursor(row)
    result = read_exact_run_for_verified_actor(
        cursor, actor_id="oidc:alice", run_id="RUN-A")
    assert result == dict(zip(RUN_FIELDS, row))
    assert cursor.calls == [(EXACT_RUN_FOR_ACTOR_SQL, ("RUN-A", "oidc:alice"))]
    assert "g.revoked_at is null" in EXACT_RUN_FOR_ACTOR_SQL
    assert "b.run_id = r.run_id" in EXACT_RUN_FOR_ACTOR_SQL
    assert "g.tenant_id = b.tenant_id" in EXACT_RUN_FOR_ACTOR_SQL

    # Missing or unauthorized rows are deliberately indistinguishable.
    cursor = Cursor(None)
    assert read_exact_run_for_verified_actor(
        cursor, actor_id="oidc:alice", run_id="RUN-FOREIGN") is None
    assert cursor.calls[0][1] == ("RUN-FOREIGN", "oidc:alice")


def test_core_exact_run_rejects_client_scopes_before_sql():
    cursor = Cursor(None)
    for actor, run in (
        ("", "RUN-A"), ("bad actor", "RUN-A"),
        ("oidc:alice", ""), ("oidc:alice", "not-a-run"),
        ("oidc:alice", "RUN-A' OR TRUE --"),
        (None, "RUN-A"), ("oidc:alice", None),
    ):
        with pytest.raises(ValueError):
            read_exact_run_for_verified_actor(
                cursor, actor_id=actor, run_id=run)
    assert cursor.calls == []


def test_exact_run_bearer_checks_revocation_before_opening_read_connection(monkeypatch):
    import types
    from core.portal_tenant_runs import read_exact_run_for_bearer

    events = []
    class Connection:
        def __init__(self):
            self.cursor_obj = Cursor(None)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def cursor(self):
            class CursorContext:
                def __enter__(inner):
                    return self.cursor_obj
                def __exit__(inner, *args):
                    return False
            return CursorContext()
        def close(self):
            events.append("close")

    def connect():
        events.append("connect")
        return Connection()

    def store(factory):
        assert factory is connect
        events.append("store")
        return (lambda **kwargs: False), None, None

    def verified(token, *, is_revoked):
        events.append("identity")
        assert token == "synthetic-oidc-fixture"
        assert is_revoked(issuer="https://issuer.example", jti="jti-a") is False
        return types.SimpleNamespace(actor_id="oidc:alice")

    import shared.oidc_jti_store as jti_module
    import shared.verified_principal as principal_module
    monkeypatch.setattr(jti_module, "make_oidc_jti_store", store)
    monkeypatch.setattr(principal_module, "principal_from_bearer", verified)

    assert read_exact_run_for_bearer(
        connect, bearer_token="synthetic-oidc-fixture", run_id="RUN-A") is None
    assert events == ["store", "identity", "connect", "close"]

    events.clear()
    def denied(token, *, is_revoked):
        events.append("identity-denied")
        raise ValueError("revoked or invalid identity")
    monkeypatch.setattr(principal_module, "principal_from_bearer", denied)
    with pytest.raises(ValueError):
        read_exact_run_for_bearer(
            connect, bearer_token="synthetic-oidc-fixture", run_id="RUN-A")
    assert events == ["store", "identity-denied"]

    events.clear()
    with pytest.raises(ValueError):
        read_exact_run_for_bearer(
            connect, bearer_token="synthetic-oidc-fixture", run_id="bad-run")
    assert events == []
