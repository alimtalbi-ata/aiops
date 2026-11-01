"""Disposable real HTTPS Chromium/API actor-resource denial E2E; synthetic only.

Imported by the existing Quality Playwright entry point. No IdP/GLPI/Core
network, no bearer delegation, no writes, no positive ACL or LIVE.
"""
from __future__ import annotations

import base64
import copy
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import sync_playwright
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


class PortalACLChromiumE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="portal-acl-disposable-")
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(cls.key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
                .add_extension(x509.SubjectAlternativeName([
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                .sign(cls.key, hashes.SHA256()))
        certfile, keyfile = (Path(cls.tmp.name) / n for n in ("cert.pem", "key.pem"))
        certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile.write_bytes(cls.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        cls.settings = {
            "AIOPS_INTERNAL_TOKEN": "internal-" + "i" * 48,
            "AIOPS_PORTAL_READ_TOKEN": "viewer-" + "v" * 40,
            "AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": "xref-" + "x" * 40,
            "AIOPS_PORTAL_CORE_XREF_SCOPE": "itsm:xref:read",
            "AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": "authz-" + "s" * 40,
            "AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "actor:resource:authorize",
        }
        cls.env = patch.dict(os.environ, cls.settings)
        cls.env.start()
        try:
            from portal import main, oidc_session, acme_run_detail, core_authz_transport
            from portal.oidc_identity import PortalActorContext
            cls.main, cls.sessions, cls.detail = main, oidc_session, acme_run_detail
            cls.wire, cls.Actor = core_authz_transport, PortalActorContext
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                cls.port = sock.getsockname()[1]
            cls.base = f"https://127.0.0.1:{cls.port}"
            cls.server = uvicorn.Server(uvicorn.Config(
                main.app, host="127.0.0.1", port=cls.port,
                ssl_keyfile=str(keyfile), ssl_certfile=str(certfile),
                log_level="error", lifespan="off"))
            cls.thread = threading.Thread(target=cls.server.run, daemon=True)
            cls.thread.start()
            for _ in range(100):
                if cls.server.started:
                    break
                if not cls.thread.is_alive():
                    raise RuntimeError("disposable TLS Portal exited")
                time.sleep(.1)
            else:
                raise RuntimeError("disposable TLS Portal startup timeout")
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "pw"):
            cls.pw.stop()
        if hasattr(cls, "server"):
            cls.server.should_exit = True
        if hasattr(cls, "thread"):
            cls.thread.join(timeout=10)
        if hasattr(cls, "env"):
            cls.env.stop()
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def setUp(self):
        with self.sessions._lock:
            self.sessions._pending.clear()
            self.sessions._sessions.clear()
        self.context = self.browser.new_context(
            ignore_https_errors=True, service_workers="block", accept_downloads=False)
        self.observed, self.blocked = [], []
        def fence(route):
            req = route.request
            self.observed.append((req.url, dict(req.headers)))
            if req.url.startswith(self.base + "/") and req.method in ("GET", "POST"):
                route.continue_()
            else:
                self.blocked.append(req.url)
                route.abort()
        self.context.route("**/*", fence)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        with self.sessions._lock:
            self.sessions._pending.clear()
            self.sessions._sessions.clear()

    def session(self, tenant="ACME", ttl=600, actor_ttl=600):
        handle = "A" * 43
        now = int(time.time())
        actor = self.Actor("operator-123", tenant, ("N2",),
                           "https://idp.example.test/realms/acme", "aiops2-portal",
                           expires_at=now + actor_ttl)
        with self.sessions._lock:
            self.sessions._sessions[self.sessions._digest(handle)] = (
                self.sessions._Session(actor, now + ttl))
        self.context.add_cookies([{
            "name": self.sessions._SESSION_COOKIE, "value": handle,
            "url": self.base + "/", "secure": True, "httpOnly": True,
            "sameSite": "Lax",
        }])
        return actor, handle

    def assert_denied(self, response, status):
        self.assertEqual(response.status, status)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertIn("frame-ancestors 'none'",
                      response.headers.get("content-security-policy", ""))
        for secret in ("CONNECTED", "operator-123", "INC-ACME-123", "glpi-acme",
                       self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]):
            self.assertNotIn(secret, response.text())

    def test_01_anonymous_forged_headers_are_not_identity(self):
        results = []
        for run in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
            response = self.context.request.get(self.base + "/api/portal/runs/" + run,
                headers={"Authorization": "Bearer forged", "X-Actor-ID": "manager",
                         "X-Tenant-ID": "ACME", "X-GLPI-Entity": "42"})
            self.assert_denied(response, 401)
            results.append(response.json())
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assert_denied(self.page.goto(self.base + "/runs/RUN-FOREIGN-999"), 401)

    def test_02_valid_foreign_forged_runs_are_identical_unknown_no_fetch(self):
        results = []
        with patch.object(self.detail, "_read_core_run",
                          side_effect=AssertionError("Core read forbidden")) as core, \
             patch.object(self.main, "get_json",
                          side_effect=AssertionError("upstream forbidden")) as upstream, \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("network forbidden")) as network:
            for tenant in ("ACME", "FOREIGN"):
                self.session(tenant)
                for run in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
                    response = self.context.request.get(self.base + "/api/portal/runs/" + run,
                        headers={"Authorization": "Bearer forged", "X-Actor-ID": "admin",
                                 "X-Tenant-ID": "ACME", "X-GLPI-Ticket": "123",
                                 "X-GLPI-Entity": "42"})
                    self.assert_denied(response, 503)
                    results.append(response.json())
                self.assert_denied(self.page.goto(
                    self.base + "/runs/RUN-FOREIGN-999"), 503)
            core.assert_not_called()
            upstream.assert_not_called()
            network.assert_not_called()
        self.assertTrue(all(x == results[0] for x in results))
        self.assertEqual(results[0]["state"], "UNKNOWN")
        self.assertNotIn("run_id", results[0])
        self.assertNotIn("ticket_id", results[0])

    def test_03_revoked_expired_and_replayed_session(self):
        _, handle = self.session()
        self.assert_denied(self.context.request.get(
            self.base + "/api/portal/runs/RUN-ACME-123"), 503)
        with self.sessions._lock:
            self.sessions._sessions.pop(self.sessions._digest(handle), None)
        for _ in range(2):
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 401)
            self.assert_denied(self.page.goto(self.base + "/runs/RUN-ACME-123"), 401)
        self.session(ttl=-1)
        self.assert_denied(self.context.request.get(
            self.base + "/api/portal/runs/RUN-ACME-123"), 401)
        self.session(actor_ttl=-1)
        self.assert_denied(self.context.request.get(
            self.base + "/api/portal/runs/RUN-ACME-123"), 401)

    def test_04_signed_allow_replay_and_cross_resource_still_denied(self):
        from portal.core_acl_consumer import ServerXref
        from test_portal_core_acl_consumer import PortalCoreACLConsumerTests
        actor, _ = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        now = int(time.time())
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=now)
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        _, _, _, payload = PortalCoreACLConsumerTests().future_envelope(now)
        payload["request_nonce"] = plan.nonce
        public = self.key.public_key().public_numbers()
        def b64_int(value):
            return base64.urlsafe_b64encode(value.to_bytes(
                (value.bit_length() + 7) // 8, "big")).rstrip(b"=").decode("ascii")
        settings = {**self.settings, "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON":
                    json.dumps({"keys": [{"kid": "disposable-core", "kty": "RSA",
                                          "alg": "RS256", "use": "sig",
                                          "n": b64_int(public.n), "e": b64_int(public.e)}]})}
        def sign(body):
            signature = self.key.sign(
                self.wire._canonical_signed_bytes(plan.origin, body),
                padding.PKCS1v15(), hashes.SHA256())
            return {"alg": "RS256", "kid": "disposable-core", "signature":
                    base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")}
        signature = sign(payload)
        def verify(body, sig, target=plan):
            return self.wire.verify_pinned_core_response_signature(
                body, sig, actor=actor, binding=binding, plan=target,
                env=settings, now=now)
        self.assertTrue(verify(payload, signature))  # synthetic signature, NOT ACL
        self.assertFalse(self.wire.core_authz_read_permitted(payload, signature))
        fresh = self.wire.prepare_core_authz_wire(
            actor, binding, env=settings, now=now)
        self.assertNotEqual(plan.nonce, fresh.nonce)
        self.assertFalse(verify(payload, signature, fresh))
        for change in ({"tenant_id": "FOREIGN"}, {"run_id": "RUN-FOREIGN-999"},
                       {"ticket_id": "999"}, {"glpi_entity_id": "99"},
                       {"actor_subject": "forged"},
                       {"actor_issuer": "https://evil.test"},
                       {"actor_audience": "evil-client"}, {"expires_at": now - 1}):
            with self.subTest(change=change):
                altered = {**copy.deepcopy(payload), **change}
                self.assertFalse(verify(altered, sign(altered)))
        self.assertFalse(verify(payload, {**signature, "signature": "A" * 43}))
        self.assert_denied(self.context.request.get(
            self.base + "/api/portal/runs/RUN-ACME-123"), 503)

    def test_05_browser_never_receives_service_bearer_or_glpi_write(self):
        self.session()
        self.page.goto(self.base + "/runs/RUN-ACME-123")
        self.page.goto(self.base + "/itsm")
        # ITSM currently uses its own legacy viewer gate, not the OIDC
        # identity cookie. A valid OIDC session cannot bypass that gate.
        status = self.context.request.get(self.base + "/api/portal/itsm")
        self.assert_denied(status, 401)
        self.assertFalse(status.json().get("glpi_write_enabled", False))
        legacy = self.context.request.get(self.base + "/api/portal/itsm",
            headers={"Authorization": "Bearer " + self.settings["AIOPS_PORTAL_READ_TOKEN"]})
        self.assert_denied(legacy, 503)
        self.assertFalse(legacy.json()["glpi_write_enabled"])
        self.assertIn("NOT_INSTALLED", self.page.locator("body").inner_text())
        self.assertTrue(self.page.locator("#priority").is_disabled())
        self.assertTrue(self.observed)
        for url, headers in self.observed:
            self.assertTrue(url.startswith(self.base + "/"))
            self.assertNotIn("authorization", headers)
            for token in (self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"],
                          self.settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"]):
                self.assertNotIn(token, str(headers))
                self.assertNotIn(token, self.page.content())
        self.assertFalse(self.blocked)
