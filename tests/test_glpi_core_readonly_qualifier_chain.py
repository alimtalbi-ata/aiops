"""Full isolated Core+GLPI read-only qualification with real security adapters.

Only the signed-xref/OIDC resolver and external PostgreSQL/vault/HTTPS servers
are controlled fixtures. No real IdP, GLPI, Core or credentials are used.
"""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.verified_principal_glpi_readonly import (
    VerifiedGLPIReadbackBlocked, make_verified_principal_glpi_readonly_qualifier,
)

ACTOR = "oidc:" + "a" * 64
RUN = "RUN-ABCDEFGH1234"
ASSOCIATION = dict(actor=ACTOR, tenant_id="tenant-a",
                   glpi_instance_id="glpi-a", glpi_entity_id="7",
                   ticket_id="42", incident_id="INC-OPS-1234", run_id=RUN)


class Cursor:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params):
        assert params == (ACTOR, "tenant-a", "glpi-a")
    def fetchall(self): return [(17,)]


class DB:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def cursor(self): return Cursor()
    def close(self): pass


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, payload): self.data = io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.data.read(n)


class FakeHTTPS:
    def __init__(self, *, glpi_user=17, glpi_entity=7,
                 incident="INC-OPS-1234", core_mode="DEMO"):
        self.glpi_user = glpi_user
        self.glpi_entity = glpi_entity
        self.incident = incident
        self.core_mode = core_mode
        self.calls = []
    def open(self, request, timeout):
        url = request.full_url
        self.calls.append((request.get_method(), url))
        assert request.get_method() == "GET"
        if url.endswith("/initSession"):
            assert request.get_header("Authorization") == "user_token isolated-user-secret"
            return Response({"session_token": "isolated-session"})
        if url.endswith("/getFullSession"):
            return Response({"session": {"glpiID": self.glpi_user}})
        if url.endswith("/Ticket/42"):
            return Response({"id": 42, "entities_id": self.glpi_entity})
        if url.endswith("/killSession"):
            return Response({})
        if url.endswith("/api/runs/" + RUN):
            assert request.get_header("Authorization") == "Bearer isolated-core-secret"
            return Response({"run": {"run_id": RUN, "incident_id": self.incident,
                                     "mode": self.core_mode}})
        raise AssertionError(url)


def make_qualifier(server, *, core_allowed=True, glpi_allowed=True):
    def resolver_factory(**kwargs):
        assert callable(kwargs["authorize_glpi_native_acl"])
        def resolve(bearer, ticket):
            assert bearer == "isolated-oidc-bearer"
            assert ticket == "42"
            # Invoke the real native GLPI ACL: OIDC/xref itself is separately
            # covered by its own unit and PostgreSQL integration tests.
            assert kwargs["authorize_glpi_native_acl"](
                actor=ACTOR, tenant_id="tenant-a",
                glpi_instance_id="glpi-a", glpi_entity_id="7",
                ticket_id="42", action="read_ticket",
            ) is True
            return dict(ASSOCIATION)
        return resolve
    with patch("shared.glpi_session_readonly.build_opener", return_value=server), \\
         patch("shared.glpi_http_json_transport.build_opener", return_value=server), \\
         patch("shared.verified_principal_glpi_readonly.make_verified_principal_glpi_xref_resolver",
               side_effect=resolver_factory):
        return make_verified_principal_glpi_readonly_qualifier(
            connect=lambda: DB(), secret=b"x" * 32,
            fetch_signed_event=lambda **_: None,
            authorize_core_read=lambda **_: core_allowed,
            authorize_glpi_read=lambda **_: glpi_allowed,
            core_token=lambda **_: "isolated-core-secret",
            glpi_app_token=lambda **_: "isolated-app-secret",
            get_bound_glpi_credential=lambda **scope: dict(
                glpi_user_id=17, glpi_instance_id=scope["glpi_instance_id"],
                tenant_id=scope["tenant_id"], user_token="isolated-user-secret",
            ),
            core_base_url="https://core.example.invalid",
            glpi_base_url="https://glpi.example.invalid",
        )


def test_full_isolated_qualifier_matches_independent_core_and_glpi_readbacks():
    server = FakeHTTPS()
    qualify = make_qualifier(server)
    result = qualify(bearer_token="isolated-oidc-bearer", ticket_id="42")
    assert result["raw_readbacks_match"] is True
    assert result["run_id"] == RUN
    assert result["execution_allowed"] is False
    assert result["copilot_query_performed"] is False
    assert result["glpi_write_performed"] is False
    paths = [url.split(".invalid")[-1] for _, url in server.calls]
    assert paths.count("/apirest.php/getFullSession") == 2
    assert paths.count("/apirest.php/killSession") == 2
    assert paths.count("/apirest.php/Ticket/42") == 2
    assert paths.count("/api/runs/" + RUN) == 1


@pytest.mark.parametrize("changes", [
    {"glpi_user": 18},
    {"glpi_entity": 8},
    {"incident": "INC-OPS-WRONG"},
    {"core_mode": "LIVE"},
])
def test_full_qualifier_denies_wrong_session_entity_incident_or_live_core(changes):
    server = FakeHTTPS(**changes)
    qualify = make_qualifier(server)
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        qualify(bearer_token="isolated-oidc-bearer", ticket_id="42")


@pytest.mark.parametrize("core_allowed,glpi_allowed", [(False, True), (True, False)])
def test_full_qualifier_denies_when_independent_read_acl_denies(core_allowed, glpi_allowed):
    server = FakeHTTPS()
    qualify = make_qualifier(server, core_allowed=core_allowed, glpi_allowed=glpi_allowed)
    with pytest.raises(VerifiedGLPIReadbackBlocked):
        qualify(bearer_token="isolated-oidc-bearer", ticket_id="42")
    paths = [url.split(".invalid")[-1] for _, url in server.calls]
    if not core_allowed:
        assert "/api/runs/" + RUN not in paths
    if not glpi_allowed:
        assert paths.count("/apirest.php/Ticket/42") == 1  # native ACL only
