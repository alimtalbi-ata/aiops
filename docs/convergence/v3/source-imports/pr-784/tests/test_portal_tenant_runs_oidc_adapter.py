"""Verified OIDC -> durable JTI -> actor/tenant Runs reader contract."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.hitl_identity import IdentityError
from core.portal_tenant_runs import read_runs_for_bearer


class Cursor:
    def __init__(self, revoked_row=None, rows=()):
        self.revoked_row = revoked_row
        self.rows = rows
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self
    def fetchone(self): return self.revoked_row
    def fetchall(self): return self.rows


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor
    def close(self): self.closed = True


CLAIMS = {
    "subject_id": "oidc:" + "d" * 64,
    "issuer": "https://issuer.example.invalid",
    "roles": ["operator"],
    "groups": ["stable-operator-group"],
    "mapping_version": "groups-v1",
    "jti": "reader-jti-1",
    "expires_at": 2_100_000_000,
    "simulated": False,
}


def test_bearer_reader_derives_actor_only_from_oidc_and_applies_tenant_sql():
    revocation_cursor = Cursor(revoked_row=None)
    runs_cursor = Cursor(rows=[
        ("RUN-1", "INC-1", "DEMO", "SCN-1", "FAILED", 1, 0.9, None, None, None)
    ])
    connections = iter([Connection(revocation_cursor), Connection(runs_cursor)])
    opened = []
    def connect():
        connection = next(connections)
        opened.append(connection)
        return connection

    with patch("shared.verified_principal.verify_oidc_assertion", return_value=CLAIMS):
        result = read_runs_for_bearer(connect, bearer_token="verified-token", limit=12)

    assert [item["run_id"] for item in result["items"]] == ["RUN-1"]
    assert len(opened) == 2
    revoke_sql, revoke_params = revocation_cursor.calls[0]
    assert "oidc_jti_revocations" in revoke_sql
    assert revoke_params == (CLAIMS["issuer"], CLAIMS["jti"])
    runs_sql, runs_params = runs_cursor.calls[0]
    assert "portal_run_tenant_bindings" in runs_sql
    assert "portal_actor_tenant_grants" in runs_sql
    assert "g.revoked_at is null" in runs_sql
    assert runs_params == (CLAIMS["subject_id"], 12)
    assert all(connection.closed for connection in opened)


def test_revoked_bearer_is_denied_before_any_runs_query():
    revocation_connection = Connection(Cursor(revoked_row=(1,)))
    opened = []
    def connect():
        opened.append(revocation_connection)
        return revocation_connection

    with patch("shared.verified_principal.verify_oidc_assertion", return_value=CLAIMS):
        with pytest.raises(IdentityError, match="oidc_assertion_revoked_or_store_unavailable"):
            read_runs_for_bearer(connect, bearer_token="revoked-token")

    assert len(opened) == 1
    assert len(revocation_connection._cursor.calls) == 1
    assert "oidc_jti_revocations" in revocation_connection._cursor.calls[0][0]


def test_revocation_database_outage_fails_closed_before_runs_query():
    def unavailable():
        raise RuntimeError("postgres unavailable")

    with patch("shared.verified_principal.verify_oidc_assertion", return_value=CLAIMS):
        with pytest.raises(IdentityError, match="oidc_assertion_revoked_or_store_unavailable"):
            read_runs_for_bearer(unavailable, bearer_token="token")


def test_reader_has_no_browser_actor_or_tenant_override_parameters():
    import inspect
    params = inspect.signature(read_runs_for_bearer).parameters
    assert set(params) == {"connect", "bearer_token", "limit"}
    assert "actor_id" not in params
    assert "tenant_id" not in params
