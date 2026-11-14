import hashlib
import hmac
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.hitl_identity import IdentityError
from shared.glpi_xref_hmac_verifier import canonical_event_bytes
from shared.verified_principal_glpi_xref import (
    VerifiedGLPIXrefDenied,
    make_verified_principal_glpi_xref_resolver,
)


SECRET = b"glpi-xref-test-signing-secret-32-bytes-minimum"
NOW = 1_800_000_000
PRINCIPAL_CLAIMS = {
    "subject_id": "oidc:" + "e" * 64,
    "issuer": "https://issuer.example.invalid",
    "roles": ["operator"],
    "groups": ["stable-ops"],
    "mapping_version": "v1",
    "jti": "oidc-jti-1",
    "expires_at": NOW + 300,
    "simulated": False,
}


class Cursor:
    def __init__(self, *, revoked=False, membership=True):
        self.revoked = revoked
        self.membership = membership
        self.sql = ""
        self.params = ()
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.sql, self.params = sql, params
        self.calls.append((sql, params))
        return self
    def fetchone(self):
        if "oidc_jti_revocations" in self.sql:
            return (1,) if self.revoked else None
        if "portal_actor_tenant_grants" in self.sql:
            return (1,) if self.membership else None
        if "glpi_xref_consumed_nonces" in self.sql:
            return (self.params[1],)
        return None
    def fetchall(self):
        if "SELECT tenant_id FROM aiops.portal_actor_tenant_grants" in self.sql:
            return [("tenant-a",), ("tenant-b",)]
        return []


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor
    def close(self): self.closed = True


def signed_event(tenant_id="tenant-b"):
    claims = {
        "aud": "aiops-glpi-copilot-xref",
        "iss": "aiops-core-xref-signer",
        "actor": PRINCIPAL_CLAIMS["subject_id"],
        "tenant_id": tenant_id,
        "ticket_id": "42",
        "iat": NOW - 1,
        "exp": NOW + 120,
        "nonce": "nonce0123456789abcdef",
        "association_state": "ACTIVE",
        "association_count": 1,
        "glpi_instance_id": "glpi-prod-eu",
        "glpi_entity_id": "17",
        "incident_id": "INC-OPS-1234",
        "run_id": "RUN-ABCDEFGH1234",
    }
    signature = hmac.new(SECRET, canonical_event_bytes(claims), hashlib.sha256).hexdigest()
    return {"claims": claims, "signature": signature}


def test_resolver_derives_actor_and_tenant_from_oidc_grants_and_signed_xref():
    cursors = []
    def connect():
        cursor = Cursor()
        cursors.append(cursor)
        return Connection(cursor)

    fetches = []
    def fetch_signed_event(*, actor, tenant_id, ticket_id):
        fetches.append((actor, tenant_id, ticket_id))
        return signed_event(tenant_id) if tenant_id == "tenant-b" else None

    acl_calls = []
    def native_acl(**kwargs):
        acl_calls.append(kwargs)
        return True

    with patch("shared.verified_principal.verify_oidc_assertion", return_value=PRINCIPAL_CLAIMS):
        resolve = make_verified_principal_glpi_xref_resolver(
            connect=connect, secret=SECRET,
            fetch_signed_event=fetch_signed_event,
            authorize_glpi_native_acl=native_acl, clock=lambda: NOW,
        )
    result = resolve("verified-bearer", "42")

    assert result["tenant_id"] == "tenant-b"
    assert result["actor"] == PRINCIPAL_CLAIMS["subject_id"]
    assert fetches == [
        (PRINCIPAL_CLAIMS["subject_id"], "tenant-a", "42"),
        (PRINCIPAL_CLAIMS["subject_id"], "tenant-b", "42"),
    ]
    assert acl_calls == [{
        "actor": PRINCIPAL_CLAIMS["subject_id"],
        "tenant_id": "tenant-b",
        "glpi_instance_id": "glpi-prod-eu",
        "glpi_entity_id": "17",
        "ticket_id": "42",
        "action": "read_ticket",
    }]
    sql = [call for cursor in cursors for call in cursor.calls]
    assert any("oidc_jti_revocations" in statement for statement, _ in sql)
    assert any("portal_actor_tenant_grants" in statement and "revoked_at IS NULL" in statement for statement, _ in sql)
    assert any("glpi_xref_consumed_nonces" in statement for statement, _ in sql)


def test_revoked_oidc_jti_denies_before_tenant_discovery_or_glpi_acl():
    cursors = []
    def connect():
        cursor = Cursor(revoked=True)
        cursors.append(cursor)
        return Connection(cursor)
    acl = []
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=PRINCIPAL_CLAIMS):
        with pytest.raises(IdentityError, match="oidc_assertion_revoked_or_store_unavailable"):
            resolve = make_verified_principal_glpi_xref_resolver(
                connect=connect, secret=SECRET,
                fetch_signed_event=lambda **_: signed_event(),
                authorize_glpi_native_acl=lambda **kwargs: acl.append(kwargs) or True,
                clock=lambda: NOW,
            )
            resolve("revoked", "42")
    assert len(cursors) == 1
    assert acl == []


def test_native_glpi_acl_must_return_exact_true():
    def connect():
        return Connection(Cursor())
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=PRINCIPAL_CLAIMS):
        resolve = make_verified_principal_glpi_xref_resolver(
            connect=connect, secret=SECRET,
            fetch_signed_event=lambda **kwargs: signed_event(kwargs["tenant_id"]),
            authorize_glpi_native_acl=lambda **kwargs: 1,
            clock=lambda: NOW,
        )
    with pytest.raises(VerifiedGLPIXrefDenied, match="signed_xref_not_authorized"):
        resolve("token", "42")


def test_ticket_resolver_has_no_caller_actor_or_tenant_override():
    def connect():
        return Connection(Cursor())
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=PRINCIPAL_CLAIMS):
        resolve = make_verified_principal_glpi_xref_resolver(
            connect=connect, bearer_token="token", secret=SECRET,
            fetch_signed_event=lambda **kwargs: signed_event(kwargs["tenant_id"]),
            authorize_glpi_native_acl=lambda **kwargs: True,
            clock=lambda: NOW,
        )
    import inspect
    assert list(inspect.signature(resolve).parameters) == ["bearer_token", "ticket_id"]
    with pytest.raises(VerifiedGLPIXrefDenied, match="invalid_ticket_id"):
        resolve("token", "../42")
