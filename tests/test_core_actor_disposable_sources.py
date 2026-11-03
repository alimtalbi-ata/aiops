"""Three independently running disposable IdP, subject-map and GLPI mock servers.

All sockets bind 127.0.0.1; HTTPS URL routing is simulated by a test-only
bridge, NOT a TLS/certificate qualification. No real IdP or GLPI is contacted.
The native source preflight is necessary but never authorizes ALLOW.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs

import requests
from core import actor_native_authority as native
from core import actor_resource_authz as actor

KEY = "disposable-source-map-key-000000000000000001"
ISSUER = "https://issuer.example.invalid"
EXPECTED = {"tenant_id": "TEN-A", "run_id": "RUN-A",
            "incident_id": "INC-A", "glpi_instance_id": "GLPI-A",
            "ticket_id": "123", "glpi_entity_id": "7",
            "permission": "run:read",
            "nonce": "nonce-disposable-source-000001"}
CONFIG = {"tenant_id": "TEN-A", "glpi_instance_id": "GLPI-A",
          "mapping_url": "https://identity.example.invalid/map",
          "mapping_client_id": "mapping-client-identity",
          "mapping_client_secret": "mapping-secret-only-for-disposable-ci-0001",
          "mapping_mac_key": KEY, "glpi_origin": "https://glpi.example.invalid",
          "glpi_app_token": "glpi-app-token-disposable-only"}
IDP = {"url": "https://idp.example.invalid/introspect",
       "issuer": ISSUER, "audience": "aiops-core",
       "client_id": "actor-introspection-client",
       "client_secret": "actor-introspection-secret-disposable-00001"}
REAL_SESSION = requests.Session


class AuthorityHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, value, code=200):
        data = json.dumps(value).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        server = self.server
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size < 8192:
            return self.respond({}, 400)
        raw = self.rfile.read(size)
        payload = (parse_qs(raw.decode("utf-8")) if self.server.role == "idp"
                   else json.loads(raw))
        server.calls.append((self.path, payload))
        auth = self.headers.get("Authorization", "")
        if server.role == "idp":
            basic = base64.b64encode(
                (IDP["client_id"] + ":" + IDP["client_secret"]).encode()).decode()
            if auth != "Basic " + basic or self.path != "/introspect":
                return self.respond({}, 401)
            return self.respond(server.claims)
        if server.role == "mapping":
            basic = base64.b64encode(
                (CONFIG["mapping_client_id"] + ":" +
                 CONFIG["mapping_client_secret"]).encode()).decode()
            if auth != "Basic " + basic or self.path != "/map":
                return self.respond({}, 401)
            mapping = dict(payload, schema_version="aiops.core-oidc-glpi-actor-binding.v1",
                           source_event_id="IDMAP-DISPOSABLE", issued_at=server.now-10,
                           expires_at=server.now+90, revoked=server.revoked,
                           glpi_session_token="human-session-disposable-00001")
            mapping["binding_mac"] = native._mapping_mac(mapping, KEY)
            return self.respond(mapping)
        return self.respond({}, 404)

    def do_GET(self):
        server = self.server
        server.calls.append((self.path, None))
        if (server.role != "glpi" or
                self.headers.get("App-Token") != CONFIG["glpi_app_token"] or
                self.headers.get("Session-Token") != "human-session-disposable-00001"):
            return self.respond({}, 401)
        rows = {
            "/apirest.php/getFullSession": {"session": {
                "glpiID": 47, "glpiactiveprofile": {"id": 2},
                "glpiactiveentities": [7]}},
            "/apirest.php/User/47": {"id": 47, "is_active": 1},
            "/apirest.php/Profile/2": {"id": 2, "ticket": server.ticket_right},
            "/apirest.php/Entity/7": {"id": 7},
            "/apirest.php/Ticket/123": {"id": 123, "entities_id": server.entity},
        }
        return self.respond(rows.get(self.path, {}))


class LoopbackTransport:
    """Preserve production HTTPS flags; route only pinned synthetic origins."""
    def __init__(self, ports):
        self.ports = ports
        self.trust_env = True
        self.real = REAL_SESSION()
        self.real.trust_env = False
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.real.close()
    def request(self, method, url, **kw):
        assert self.trust_env is False
        assert kw["verify"] is True and kw["allow_redirects"] is False
        assert kw["stream"] is True and kw["timeout"] == (2, 3)
        for origin, port in self.ports.items():
            if url.startswith(origin + "/"):
                return self.real.request(
                    method, "http://127.0.0.1:" + str(port) + url[len(origin):],
                    **{**kw, "verify": False})
        raise AssertionError("unexpected external network URL: " + url)
    def get(self, url, **kw):
        return self.request("GET", url, **kw)
    def post(self, url, **kw):
        return self.request("POST", url, **kw)


class DisposableHumanAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.claims = dict(active=True, revoked=False, iss=ISSUER,
                           aud=IDP["audience"], sub="idp|alice",
                           iat=self.now-10, nbf=self.now-5, exp=self.now+120,
                           jti="JTI_disposable_0000000000000001",
                           glpi_user_id=47, permissions=["run:read"], **EXPECTED)
        self.servers = {}
        for role in ("idp", "mapping", "glpi"):
            server = ThreadingHTTPServer(("127.0.0.1", 0), AuthorityHandler)
            server.role, server.calls, server.now = role, [], self.now
            server.claims, server.revoked = self.claims, False
            server.ticket_right, server.entity = 1, 7
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers[role] = (server, thread)
        ports = {"https://idp.example.invalid": self.servers["idp"][0].server_port,
                 "https://identity.example.invalid": self.servers["mapping"][0].server_port,
                 "https://glpi.example.invalid": self.servers["glpi"][0].server_port}
        self.env = patch.dict(os.environ, {
            "AIOPS_XREF_ACTOR_INTROSPECTION_JSON": json.dumps(IDP),
            "AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": json.dumps([CONFIG])})
        self.env.start()
        self.transport = patch.object(requests, "Session",
                                      side_effect=lambda: LoopbackTransport(ports))
        self.transport.start()

    def tearDown(self):
        self.transport.stop()
        self.env.stop()
        for server, thread in self.servers.values():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def preflight(self, expected=None):
        expected = expected or EXPECTED
        claims = actor._actor_introspection(
            "opaque-delegation-disposable-token", expected, self.now)
        return claims, (native._native_glpi_preflight(claims, expected, self.now)
                        if claims is not None else False)

    def test_three_separate_authorities_are_consulted_but_not_allow(self):
        claims, passed = self.preflight()
        self.assertIsNotNone(claims)
        self.assertTrue(passed)
        self.assertEqual([len(self.servers[k][0].calls)
                          for k in ("idp", "mapping", "glpi")], [1, 1, 5])
        self.assertEqual(actor._reply().body,
                         b'{"schema":"aiops.core-actor-resource-authorization.v1","decision":"UNKNOWN"}')

    def test_foreign_tenant_fails_before_mapping_and_glpi(self):
        claims, passed = self.preflight({**EXPECTED, "tenant_id": "TEN-B"})
        self.assertIsNone(claims)
        self.assertFalse(passed)
        self.assertEqual(len(self.servers["mapping"][0].calls), 0)
        self.assertEqual(len(self.servers["glpi"][0].calls), 0)

    def test_revoked_mapping_fails_before_glpi(self):
        self.servers["mapping"][0].revoked = True
        self.assertFalse(self.preflight()[1])
        self.assertEqual(len(self.servers["glpi"][0].calls), 0)

    def test_native_ticket_read_permission_is_required(self):
        self.servers["glpi"][0].ticket_right = 0
        self.assertFalse(self.preflight()[1])

    def test_native_ticket_entity_is_exact(self):
        self.servers["glpi"][0].entity = 8
        self.assertFalse(self.preflight()[1])

    def test_untrusted_issuer_fails_before_mapping(self):
        self.servers["idp"][0].claims = {**self.claims, "iss": "https://evil.invalid"}
        self.assertFalse(self.preflight()[1])
        self.assertEqual(len(self.servers["mapping"][0].calls), 0)


if __name__ == "__main__":
    unittest.main()
