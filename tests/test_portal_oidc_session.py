"""Disposable OIDC authorization-code/PKCE callback + revocable session tests.

Fake IdP is an in-process signed RSA fixture; no HTTP/GLPI/Core/LIVE.
"""
import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-" + "i" * 48}):
    from portal import main, oidc_session


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class PortalOIDCCallbackTests(unittest.TestCase):
    def setUp(self):
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = self.private.public_key().public_numbers()
        jwk = {"kid": "disposable", "kty": "RSA", "alg": "RS256", "use": "sig",
               "n": b64(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
               "e": b64(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big"))}
        self.config = {
            "AIOPS_PORTAL_OIDC_ISSUER": "https://idp.example.test/realms/acme",
            "AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT":
                "https://idp.example.test/realms/acme/protocol/openid-connect/auth",
            "AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT":
                "https://idp.example.test/realms/acme/protocol/openid-connect/token",
            "AIOPS_PORTAL_OIDC_REDIRECT_URI":
                "https://portal.example.test/auth/oidc/callback",
            "AIOPS_PORTAL_OIDC_CLIENT_ID": "aiops2-portal",
            "AIOPS_PORTAL_OIDC_AUDIENCE": "aiops2-portal",
            "AIOPS_PORTAL_OIDC_JWKS_JSON": json.dumps({"keys": [jwk]}),
            "AIOPS_PORTAL_OIDC_TENANT_GROUP_MAP_JSON":
                json.dumps({"acme-tenant": "ACME", "foreign-tenant": "OTHER"}),
            "AIOPS_PORTAL_OIDC_ROLE_GROUP_MAP_JSON":
                json.dumps({"noc-n2": "N2", "noc-manager": "manager"}),
        }
        self.environment = patch.dict(os.environ, self.config)
        self.environment.start()
        with oidc_session._lock:
            oidc_session._pending.clear()
            oidc_session._sessions.clear()
        self.client = TestClient(main.app, base_url="https://portal.example.test",
                                 follow_redirects=False)

    def tearDown(self):
        self.client.close()
        self.environment.stop()
        with oidc_session._lock:
            oidc_session._pending.clear()
            oidc_session._sessions.clear()

    def assert_headers(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])

    def login(self):
        response = self.client.get("/auth/oidc/login")
        self.assertEqual(response.status_code, 303)
        self.assert_headers(response)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        return response, {key: value[0] for key, value in query.items()}

    def signed_token(self, nonce, **overrides):
        now = int(time.time())
        claims = {
            "iss": self.config["AIOPS_PORTAL_OIDC_ISSUER"],
            "aud": "aiops2-portal", "sub": "operator-123",
            "iat": now - 10, "nbf": now - 10, "exp": now + 600,
            "groups": ["acme-tenant", "noc-n2"], "nonce": nonce,
        }
        claims.update(overrides)
        header = {"alg": "RS256", "typ": "JWT", "kid": "disposable"}
        unsigned = b64(json.dumps(header).encode()) + "." + b64(json.dumps(claims).encode())
        signature = self.private.sign(unsigned.encode("ascii"), padding.PKCS1v15(),
                                      hashes.SHA256())
        return unsigned + "." + b64(signature)

    def callback(self, query, id_token=None):
        if id_token is None:
            id_token = self.signed_token(query["nonce"])
        with patch.object(oidc_session, "_exchange", return_value=id_token) as exchange:
            response = self.client.get("/auth/oidc/callback",
                                       params={"code": "fixture-code", "state": query["state"]})
        return response, exchange

    def test_login_pkce_nonce_state_and_secure_cookie(self):
        response, query = self.login()
        self.assertEqual(query["response_type"], "code")
        self.assertEqual(query["code_challenge_method"], "S256")
        self.assertEqual(query["scope"], "openid")
        self.assertGreaterEqual(len(query["state"]), 32)
        self.assertGreaterEqual(len(query["nonce"]), 32)
        self.assertNotEqual(query["state"], query["nonce"])
        self.assertEqual(query["redirect_uri"],
                         self.config["AIOPS_PORTAL_OIDC_REDIRECT_URI"])
        self.assertIn("__Host-aiops_portal_oidc_state=", response.headers["set-cookie"])
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("secure", response.headers["set-cookie"].lower())
        self.assertIn("samesite=lax", response.headers["set-cookie"].lower())
        self.assertNotIn("actor", response.headers["location"])
        self.assertNotIn("tenant", response.headers["location"])

    def test_real_rsa_callback_identity_only_then_logout_revoke(self):
        _, query = self.login()
        with patch.object(main, "get_json", side_effect=AssertionError("Core read")) as read, \
             patch.object(main, "post_json", side_effect=AssertionError("Core write")) as write:
            response, exchange = self.callback(query)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/")
            self.assert_headers(response)
            self.assertEqual(exchange.call_count, 1)
            cookie = response.headers["set-cookie"]
            self.assertIn("__Host-aiops_portal_session=", cookie)
            self.assertIn("httponly", cookie.lower())
            self.assertIn("secure", cookie.lower())
            self.assertNotIn("operator-123", cookie)
            self.assertNotIn("ACME", cookie)
            status = self.client.get("/api/portal/session",
                                     headers={"X-Actor-ID": "admin",
                                              "X-Tenant-ID": "FOREIGN",
                                              "Authorization": "Bearer forged"})
            self.assertEqual(status.status_code, 503)
            self.assertEqual(status.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertNotIn("operator-123", status.text)
            self.assertNotIn("ACME", status.text)
            self.assert_headers(status)
            rejected = self.client.post("/auth/oidc/logout")
            self.assertEqual(rejected.status_code, 403)
            self.assert_headers(rejected)
            self.assertEqual(self.client.get("/api/portal/session").status_code, 503)
            logged_out = self.client.post("/auth/oidc/logout",
                                          headers={"Origin": "https://portal.example.test"})
            self.assertEqual(logged_out.status_code, 204)
            self.assert_headers(logged_out)
            self.assertEqual(self.client.get("/api/portal/session").status_code, 401)
            read.assert_not_called()
            write.assert_not_called()

    def test_forged_state_never_exchanges_or_creates_session(self):
        _, query = self.login()
        with patch.object(oidc_session, "_exchange",
                          side_effect=AssertionError("token endpoint contacted")) as upstream:
            response = self.client.get("/auth/oidc/callback",
                                       params={"code": "fixture-code", "state": "A" * 43})
        self.assertEqual(response.status_code, 401)
        self.assert_headers(response)
        self.assertEqual(self.client.get("/api/portal/session").status_code, 401)
        upstream.assert_not_called()

    def test_nonce_mismatch_and_replay_fail_closed(self):
        _, query = self.login()
        bad, exchange = self.callback(query, self.signed_token("wrong-nonce"))
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual(self.client.get("/api/portal/session").status_code, 401)
        replay, exchange = self.callback(query)
        self.assertEqual(replay.status_code, 401)
        exchange.assert_not_called()
        self.assert_headers(replay)

    def test_expired_token_and_foreign_group_never_create_session(self):
        for overrides in ({"exp": int(time.time()) - 1},
                          {"groups": ["foreign-tenant", "noc-n2"]},
                          {"aud": "another-client"}):
            with self.subTest(overrides=overrides):
                _, query = self.login()
                response, exchange = self.callback(
                    query, self.signed_token(query["nonce"], **overrides))
                # Foreign group is valid identity, not positive ACL.
                self.assertEqual(response.status_code, 303 if "groups" in overrides else 401)
                self.assert_headers(response)
                self.assertEqual(exchange.call_count, 1)
                status = self.client.get("/api/portal/session")
                self.assertEqual(status.status_code, 503 if "groups" in overrides else 401)
                self.client.post("/auth/oidc/logout",
                                 headers={"Origin": "https://portal.example.test"})

    def test_unconfigured_or_malicious_endpoints_fail_without_redirect(self):
        for override in (
            {"AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT": "https://evil.example.test/token"},
            {"AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT": "http://idp.example.test/auth"},
            {"AIOPS_PORTAL_OIDC_REDIRECT_URI": "https://idp.example.test/auth/oidc/callback"},
            {"AIOPS_PORTAL_OIDC_CLIENT_ID": "other-client"},
        ):
            with self.subTest(override=override), patch.dict(os.environ, override):
                response = self.client.get("/auth/oidc/login")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("location", response.headers)
                self.assert_headers(response)

    def test_bearer_or_forged_session_cookie_not_identity(self):
        self.client.cookies.set("__Host-aiops_portal_session", "A" * 43,
                                domain="portal.example.test", path="/")
        response = self.client.get("/api/portal/session",
                                   headers={"Authorization": "Bearer fake",
                                            "X-Tenant-ID": "ACME", "X-Actor-ID": "admin"})
        self.assertEqual(response.status_code, 401)
        self.assert_headers(response)
        self.assertNotIn("ACME", response.text)

    def test_callback_provider_error_never_exchanges(self):
        _, query = self.login()
        with patch.object(oidc_session, "_exchange",
                          side_effect=AssertionError("network")) as upstream:
            response = self.client.get("/auth/oidc/callback",
                                       params={"state": query["state"], "error": "access_denied"})
        self.assertEqual(response.status_code, 401)
        upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
