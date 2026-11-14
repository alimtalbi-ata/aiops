"""Full isolated OIDC -> HMAC xref -> nonce -> native ACL -> Core/GLPI GET.

Uses actual adapters; only IdP verification, PostgreSQL, vault and HTTPS
upstreams are controlled fixtures. No production credentials or endpoints.
"""
import hashlib
import hmac
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_glpi_core_readonly_qualifier_chain import FakeHTTPS, ACTOR, RUN
from shared.glpi_xref_hmac_verifier import canonical_event_bytes
from shared.verified_principal_glpi_readonly import (
    VerifiedGLPIReadbackBlocked, make_verified_principal_glpi_readonly_qualifier,
)

NOW = 1_800_000_000
SECRET = b"isolated-signed-xref-secret-32-bytes-minimum"
CLAIMS = dict(
    aud="aiops-glpi-copilot-xref", iss="aiops-core-xref-signer",
    actor=ACTOR, tenant_id="tenant-a", ticket_id="42",
    iat=NOW - 1, exp=NOW + 120, nonce="nonce0123456789abcdef",
    association_state="ACTIVE", association_count=1,
    glpi_instance_id="glpi-a", glpi_entity_id="7",
    incident_id="INC-OPS-1234", run_id=RUN,
)


class State:
    def __init__(self):
        self.nonces = set()
        self.revoked = False
        self.grant = True
    def connect(self): return DB(self)


class Cursor:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params):
        self.sql, self.params = sql, params
        if "INSERT INTO aiops.glpi_xref_consumed_nonces" in sql:
            key = (params[0], params[1])
            self.inserted = key not in self.state.nonces
            self.state.nonces.add(key)
    def fetchone(self):
        if "oidc_jti_revocations" in self.sql:
            return (1,) if self.state.revoked else None
        if "INSERT INTO aiops.glpi_xref_consumed_nonces" in self.sql:
            return (self.params[1],) if self.inserted else None
        if "portal_actor_tenant_grants" in self.sql:
            return (1,) if self.state.grant else None
        return None
    def fetchall(self):
        if "SELECT tenant_id FROM aiops.portal_actor_tenant_grants" in self.sql:
            return [("tenant-a",)] if self.state.grant else []
        if "glpi_actor_user_bindings" in self.sql:
            return [(17,)] if self.state.grant else []
        return []


class DB:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return Cursor(self.state)
    def close(self): pass


def event(**changes):
    claims = {**CLAIMS, **changes}
    return dict(claims=claims, signature=hmac.new(
        SECRET, canonical_event_bytes(claims), hashlib.sha256).hexdigest())


def make_chain(state, server, *, signed_event=None):
    signed_event = event() if signed_event is None else signed_event
    principal = dict(
        subject_id=ACTOR, issuer="https://issuer.example.invalid",
        roles=["operator"], groups=["ops"], mapping_version="v1",
        jti="isolated-jti", expires_at=NOW + 300, simulated=False,
    )
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=principal), \
         patch("shared.glpi_session_readonly.build_opener", return_value=server), \
         patch("shared.glpi_http_json_transport.build_opener", return_value=server):
        qualify = make_verified_principal_glpi_readonly_qualifier(
            connect=state.connect, secret=SECRET,
            fetch_signed_event=lambda **_: signed_event,
            authorize_core_read=lambda **_: True,
            authorize_glpi_read=lambda **_: True,
            core_token=lambda **_: "isolated-core-secret",
            glpi_app_token=lambda **_: "isolated-app-secret",
            get_bound_glpi_credential=lambda **scope: dict(
                glpi_user_id=17, glpi_instance_id=scope["glpi_instance_id"],
                tenant_id=scope["tenant_id"], user_token="isolated-user-secret",
            ),
            core_base_url="https://core.example.invalid",
            glpi_base_url="https://glpi.example.invalid",
            clock=lambda: NOW,
        )
        return qualify(bearer_token="isolated-oidc-bearer", ticket_id="42")


def test_full_signed_oidc_chain_success_and_durable_nonce_replay_denial():
    state = State()
    server = FakeHTTPS()
    result = make_chain(state, server)
    assert result["raw_readbacks_match"] is True
    assert result["execution_allowed"] is False
    assert state.nonces == {("tenant-a", CLAIMS["nonce"])}
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        make_chain(state, FakeHTTPS())


def test_tampered_signature_denied_before_glpi_or_core_reads():
    state = State()
    server = FakeHTTPS()
    bad = event()
    bad["claims"]["incident_id"] = "INC-OPS-TAMPERED"
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        make_chain(state, server, signed_event=bad)
    assert server.calls == []
    assert not state.nonces


def test_revoked_oidc_jti_denied_before_upstream_reads():
    state = State()
    state.revoked = True
    server = FakeHTTPS()
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        make_chain(state, server)
    assert server.calls == []
    assert not state.nonces


def test_missing_tenant_grant_denied_before_upstream_reads():
    state = State()
    state.grant = False
    server = FakeHTTPS()
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        make_chain(state, server)
    assert server.calls == []
    assert not state.nonces
