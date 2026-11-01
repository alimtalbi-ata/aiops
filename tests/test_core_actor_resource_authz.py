"""Core actor delegation negative gates. All sources are disposable mocks."""
import hashlib
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import actor_resource_authz as a
from core import itsm_xref as x

TOKEN = "ci-actor-delegation-service"
NOW = int(datetime.now(timezone.utc).timestamp())
NONCE = "ci_nonce_0123456789_0123456789"
PATH = "/api/tenants/TEN-A/runs/RUN-A/actor-resource-authorization"
BODY = {"incident_id": "INC-A", "glpi_instance_id": "GLPI-A",
        "ticket_id": "123", "glpi_entity_id": "0",
        "permission": "run:read", "nonce": NONCE}
EXPECTED = {"tenant_id": "TEN-A", "run_id": "RUN-A", **BODY}
CONFIG = {"url": "https://idp.example.invalid/oauth2/introspect",
          "issuer": "https://idp.example.invalid", "audience": "aiops-core",
          "client_id": "core-test", "client_secret": "c" * 48}
CLAIMS = {"active": True, "revoked": False, "iss": CONFIG["issuer"],
          "aud": CONFIG["audience"], "sub": "subject-123",
          "iat": NOW - 20, "nbf": NOW - 20, "exp": NOW + 60,
          "jti": "test_jti_0123456789_0123456789",
          "glpi_user_id": 42, "permissions": ["run:read"], **EXPECTED}


class FakeResponse:
    def __init__(self, payload, status=200, content_type="application/json"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.data = json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=4096):
        yield self.data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.trust_env = True
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def post(self, url, **kwargs):
        assert self.trust_env is False
        assert url == CONFIG["url"]
        assert kwargs["allow_redirects"] is False
        assert kwargs["verify"] is True
        assert kwargs["stream"] is True
        assert kwargs["auth"] == (CONFIG["client_id"], CONFIG["client_secret"])
        assert kwargs["data"]["token"] == "opaque-actor-token-123456789"
        self.calls.append(url)
        return self.response


class FakeDB:
    def __init__(self):
        self.calls = []
        self.rows = [("synthetic",)]
        self.fail = False
    @contextmanager
    def connect(self):
        yield self
    def execute(self, sql, args):
        self.calls.append((sql, args))
        if self.fail:
            raise RuntimeError("disposable database unavailable")
        return self
    def fetchall(self):
        return self.rows


def authz():
    entries = []
    for token, tenant, permissions in (
            (TOKEN, "TEN-A", ["actor:resource:authorize"]),
            ("other-tenant-token", "TEN-B", ["actor:resource:authorize"]),
            ("no-permission-token", "TEN-A", ["itsm:xref:read"])):
        entries.append({"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "actor_id": "svc-" + tenant, "tenant_ids": [tenant],
                        "permissions": permissions})
    return json.dumps(entries)


class ActorDelegationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(x.router)
        cls.client = TestClient(app)

    def setUp(self):
        self.fake = FakeDB()
        self.env = patch.dict(os.environ, {
            "AIOPS_XREF_READ_AUTHZ_JSON": authz(),
            "AIOPS_XREF_ATTESTATION_KEY": "a" * 48,
            "AIOPS_XREF_ACTOR_INTROSPECTION_JSON": json.dumps(CONFIG)})
        self.env.start()
        self.db_patch = patch.object(x, "db", self.fake.connect)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.env.stop()

    def read(self, token=TOKEN, body=None, delegation="opaque-actor-token-123456789",
             path=PATH):
        headers = {"X-Actor-Delegation": delegation}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        return self.client.post(path, json=BODY if body is None else body,
                                headers=headers, follow_redirects=False)

    def hidden(self, response):
        self.assertEqual(response.json().get("schema"), a.SCHEMA)
        self.assertNotIn("run_id", response.json())
        self.assertNotIn("incident_id", response.json())
        self.assertNotIn("ticket_id", response.json())
        self.assertNotIn("actor_subject", response.json())
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_service_401_403_before_idp_or_db(self):
        with patch.object(a, "_actor_introspection") as introspect:
            for token, code in ((None, 401), ("wrong", 401),
                                ("other-tenant-token", 403),
                                ("no-permission-token", 403)):
                with self.subTest(token=token):
                    response = self.read(token=token)
                    self.assertEqual(response.status_code, code)
                    self.hidden(response)
            introspect.assert_not_called()
        self.assertEqual(self.fake.calls, [])

    def test_invalid_exact_resource_and_nonce_have_no_upstream(self):
        bad = [
            {**BODY, "ticket_id": "RUN-123"},
            {**BODY, "incident_id": "INC/foreign"},
            {**BODY, "glpi_entity_id": "2;drop"},
            {**BODY, "permission": "itsm:write"},
            {**BODY, "nonce": "too-short"},
            {**BODY, "extra": "untrusted"},
        ]
        with patch.object(a, "_actor_introspection") as introspect:
            for payload in bad:
                response = self.read(body=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["decision"], "UNKNOWN")
                self.hidden(response)
            introspect.assert_not_called()
        self.assertEqual(self.fake.calls, [])

    def test_introspection_pinned_https_and_no_ambient_network(self):
        with patch.dict(os.environ, {"AIOPS_XREF_ACTOR_INTROSPECTION_JSON": ""}):
            with patch.object(requests, "Session") as network:
                self.assertIsNone(a._actor_introspection(
                    "opaque-actor-token-123456789", EXPECTED, NOW))
                network.assert_not_called()
        for origin in ("http://idp.example.invalid/introspect",
                       "https://evil@idp.example.invalid/introspect",
                       "https://idp.example.invalid/introspect?redirect=evil"):
            with patch.dict(os.environ, {
                    "AIOPS_XREF_ACTOR_INTROSPECTION_JSON": json.dumps(
                        {**CONFIG, "url": origin})}):
                with patch.object(requests, "Session") as network:
                    self.assertIsNone(a._actor_introspection(
                        "opaque-actor-token-123456789", EXPECTED, NOW))
                    network.assert_not_called()

    def test_introspection_requires_active_exact_short_lived_claims(self):
        good = FakeSession(FakeResponse(CLAIMS))
        with patch.object(requests, "Session", return_value=good):
            self.assertEqual(a._actor_introspection(
                "opaque-actor-token-123456789", EXPECTED, NOW), CLAIMS)
        self.assertEqual(len(good.calls), 1)
        altered = [
            {"active": False}, {"revoked": True}, {"sub": ""},
            {"iss": "https://evil.example"}, {"aud": "other"},
            {"tenant_id": "TEN-B"}, {"run_id": "RUN-B"},
            {"incident_id": "INC-B"}, {"ticket_id": "999"},
            {"glpi_entity_id": "99"}, {"nonce": "wrong"},
            {"permission": "itsm:write"}, {"permissions": []},
            {"exp": NOW - 1}, {"exp": NOW + 3600},
            {"nbf": NOW + 10}, {"glpi_user_id": True},
            {"jti": "bad"}, {"active": "true"},
        ]
        for change in altered:
            with self.subTest(change=change):
                fake = FakeSession(FakeResponse({**CLAIMS, **change}))
                with patch.object(requests, "Session", return_value=fake):
                    self.assertIsNone(a._actor_introspection(
                        "opaque-actor-token-123456789", EXPECTED, NOW))

    def test_introspection_refuses_redirect_html_and_oversize(self):
        for response in (FakeResponse(CLAIMS, status=302),
                         FakeResponse(CLAIMS, content_type="text/html"),
                         FakeResponse({"x": "a" * 17000})):
            with patch.object(requests, "Session",
                              return_value=FakeSession(response)):
                self.assertIsNone(a._actor_introspection(
                    "opaque-actor-token-123456789", EXPECTED, NOW))

    def test_hmac_verified_and_mock_glpi_still_unknown(self):
        signed = {"run_id": "RUN-A", "incident_id": "INC-A",
                  "glpi_entity_id": "0", "source_event_id": "EVT-A"}
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("VERIFIED", signed)) as evaluation:
            response = self.read()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision"], "UNKNOWN")
            self.hidden(response)
            evaluation.assert_called_once()
        self.assertEqual(len(self.fake.calls), 1)

    def test_even_synthetic_native_actor_source_pass_cannot_allow(self):
        signed = {"run_id": "RUN-A", "incident_id": "INC-A",
                  "glpi_entity_id": "0", "source_event_id": "EVT-A"}
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("VERIFIED", signed)), \
             patch("core.actor_native_authority._native_glpi_preflight",
                   return_value=True) as source, \
             patch("core.actor_run_event_source._source_run_event_preflight",
                   return_value=True) as run_source, \
             patch("core.actor_replay_fence.consume_actor_delegation",
                   return_value=True) as ledger:
            response = self.read()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision"], "UNKNOWN")
            self.hidden(response)
            source.assert_called_once()
            run_source.assert_called_once()
            ledger.assert_called_once()
        self.assertEqual(len(self.fake.calls), 1)

    def test_replay_revocation_and_ledger_unavailable_never_allow(self):
        signed = {"run_id": "RUN-A", "incident_id": "INC-A",
                  "glpi_entity_id": "0", "source_event_id": "EVT-A"}
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("VERIFIED", signed)), \
             patch("core.actor_native_authority._native_glpi_preflight",
                   return_value=True), \
             patch("core.actor_run_event_source._source_run_event_preflight",
                   return_value=True), \
             patch("core.actor_replay_fence.consume_actor_delegation") as ledger:
            for result, code in ((False, 200), (None, 503), (True, 200)):
                with self.subTest(result=result):
                    ledger.return_value = result
                    response = self.read()
                    self.assertEqual(response.status_code, code)
                    self.assertEqual(response.json()["decision"], "UNKNOWN")
                    self.hidden(response)
            self.assertEqual(ledger.call_count, 3)

    def test_no_native_actor_source_never_consumes_nonce(self):
        signed = {"run_id": "RUN-A", "incident_id": "INC-A",
                  "glpi_entity_id": "0", "source_event_id": "EVT-A"}
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("VERIFIED", signed)), \
             patch("core.actor_native_authority._native_glpi_preflight",
                   return_value=False), \
             patch("core.actor_replay_fence.consume_actor_delegation") as ledger:
            response = self.read()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision"], "UNKNOWN")
            self.hidden(response)
            ledger.assert_not_called()

    def test_missing_or_foreign_run_non_enumeration(self):
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("NOT_FOUND", None)):
            response = self.read()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision"], "UNKNOWN")
            self.hidden(response)
        with patch.object(a, "_actor_introspection", return_value=CLAIMS), \
             patch.object(x, "_evaluate", return_value=("UNAUTHORIZED", None)):
            response = self.read()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision"], "UNKNOWN")
            self.hidden(response)

    def test_db_failure_503_no_identifiers(self):
        self.fake.fail = True
        with patch.object(a, "_actor_introspection", return_value=CLAIMS):
            response = self.read()
        self.assertEqual(response.status_code, 503)
        self.hidden(response)

    def test_revoked_delegation_never_reaches_db(self):
        with patch.object(a, "_actor_introspection", return_value=None):
            response = self.read()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["decision"], "UNKNOWN")
        self.hidden(response)
        self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    unittest.main()
