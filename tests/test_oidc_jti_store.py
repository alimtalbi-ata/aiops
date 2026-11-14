import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.oidc_jti_store import make_oidc_jti_store


class FakeCursor:
    def __init__(self, row=None, fail=False):
        self.row = row
        self.fail = fail
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.calls.append((sql, params))
        if self.fail: raise RuntimeError("database unavailable")
    def fetchone(self): return self.row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor
    def close(self): self.closed = True


def test_missing_or_invalid_store_configuration_fails_closed():
    with pytest.raises(ValueError, match="postgres_connection_factory_missing"):
        make_oidc_jti_store(None)
    is_revoked, revoke, consume = make_oidc_jti_store(lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert is_revoked(issuer="https://id.example", jti="jti-1") is True
    assert revoke(issuer="https://id.example", jti="jti-1", expires_at=2_000_000_000) is False
    assert consume(issuer="https://id.example", jti="jti-1", action_id="approve:INC-1", expires_at=2_000_000_000) is False


def test_revocation_query_is_parameterized_and_database_error_denies():
    cursor = FakeCursor(row=None)
    connection = FakeConnection(cursor)
    is_revoked, _, _ = make_oidc_jti_store(lambda: connection)
    assert is_revoked(issuer="https://id.example", jti="jti-1") is False
    sql, params = cursor.calls[0]
    assert "WHERE issuer = %s AND jti = %s" in sql
    assert params == ("https://id.example", "jti-1")
    assert connection.closed
    broken = FakeConnection(FakeCursor(fail=True))
    is_revoked, _, _ = make_oidc_jti_store(lambda: broken)
    assert is_revoked(issuer="https://id.example", jti="jti-1") is True


def test_revoke_is_parameterized_and_requires_valid_expiry():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    _, revoke, _ = make_oidc_jti_store(lambda: connection)
    assert revoke(issuer="https://id.example", jti="jti-2", expires_at=2_000_000_000, reason="account_disabled")
    assert "ON CONFLICT (issuer, jti) DO UPDATE" in cursor.calls[0][0]
    assert cursor.calls[0][1][0:2] == ("https://id.example", "jti-2")
    assert not revoke(issuer=" ", jti="jti", expires_at=2_000_000_000)
    assert not revoke(issuer="https://id.example", jti="jti", expires_at=True)


def test_sensitive_action_consumption_is_atomic_insert_returning():
    cursor = FakeCursor(row=("approve:INC-1",))
    connection = FakeConnection(cursor)
    _, _, consume = make_oidc_jti_store(lambda: connection)
    assert consume(issuer="https://id.example", jti="jti-3", action_id="approve:INC-1", expires_at=2_000_000_000)
    sql, params = cursor.calls[0]
    assert "ON CONFLICT (issuer, jti, action_id) DO NOTHING" in sql
    assert "RETURNING action_id" in sql
    assert params[0:3] == ("https://id.example", "jti-3", "approve:INC-1")
    duplicate_cursor = FakeCursor(row=None)
    _, _, consume = make_oidc_jti_store(lambda: FakeConnection(duplicate_cursor))
    assert consume(issuer="https://id.example", jti="jti-3", action_id="approve:INC-1", expires_at=2_000_000_000) is False


@pytest.mark.parametrize("issuer,jti,action", [
    ("", "jti", "approve:1"),
    ("https://id.example", "", "approve:1"),
    ("https://id.example", "jti", "approve:\n1"),
    ("https://id.example", "jti", "x" * 201),
])
def test_malformed_action_never_opens_database(issuer, jti, action):
    called = []
    _, _, consume = make_oidc_jti_store(lambda: called.append(True))
    assert consume(issuer=issuer, jti=jti, action_id=action, expires_at=2_000_000_000) is False
    assert called == []
