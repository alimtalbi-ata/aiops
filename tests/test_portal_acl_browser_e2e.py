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

from portal_core_unknown_tcp_fixture import DisposableCoreUnknownTCP

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
        # A valid server OIDC session is identity-only: 503 UNKNOWN, not
        # GLPI READ/READMY. A revoked explicit cookie remains 401.
        status = self.context.request.get(self.base + "/api/portal/itsm")
        self.assert_denied(status, 503)
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

    def test_06_independent_tls_core_tcp_unknown_parity_no_browser_dispatch(self):
        """A test-only TCP Core authz POST never enables Portal business reads."""
        from portal.core_acl_consumer import ServerXref
        actor, _ = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=int(time.time()))
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        with DisposableCoreUnknownTCP() as core:
            status, payload, headers = core.send(plan)
            self.assertEqual(status, 200)
            self.assertEqual(payload, {
                "schema": "aiops.core-actor-resource-authorization.v1",
                "decision": "UNKNOWN"})
            assessment = self.wire.assess_core_authz_reply_offline(
                status, payload, headers, None, actor=actor, binding=binding,
                plan=plan, env=self.settings, now=int(time.time()))
            self.assertEqual(assessment.kind, "CURRENT_CORE_NEGATIVE")
            self.assertEqual(assessment.portal_status, 503)
            self.assertFalse(assessment.read_permitted)
            self.assertFalse(self.wire.core_authz_read_permitted(payload))
            self.assertEqual(len(core.observations), 1)
            sent = core.observations[0]
            self.assertEqual(sent["method"], "POST")
            self.assertEqual(sent["path"], plan.path)
            self.assertEqual(sent["host"], "core.example.test:8443")
            self.assertEqual(sent["authorization"],
                             "Bearer " + self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"])
            self.assertEqual(json.loads(sent["body"]), {
                "incident_id": "INC-ACME-123", "glpi_instance_id": "glpi-acme",
                "ticket_id": "123", "glpi_entity_id": "42",
                "permission": "run:read", "nonce": plan.nonce})
            self.assertNotIn("actor_subject", json.loads(sent["body"]))
            # The actual Portal is *not* wired to this test-only transport.
            for rid in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
                self.assert_denied(self.context.request.get(
                    self.base + "/api/portal/runs/" + rid), 503)
            self.assert_denied(self.page.goto(self.base + "/runs/RUN-ACME-123"), 503)
            self.assertEqual(len(core.observations), 1,
                             "Portal attempted an upstream Core read on UNKNOWN")
            for url, request_headers in self.observed:
                self.assertTrue(url.startswith(self.base + "/"))
                self.assertNotIn(self.settings[
                    "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"], str(request_headers))
                self.assertNotIn("core.example.test", url)
            self.assertNotIn(self.settings[
                "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"], self.page.content())
            self.assertFalse(self.blocked)

    def test_07_tcp_unknown_replay_foreign_revocation_and_forged_allow(self):
        """No replay or unsigned ALLOW can grant access; no GLPI identity inference."""
        from portal.core_acl_consumer import ServerXref
        actor, handle = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        now = int(time.time())
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=now)
        self.assertIsNotNone(plan)
        with DisposableCoreUnknownTCP() as core:
            first = core.send(plan)
            replay = core.send(plan)  # synthetic peer has NO durable nonce ledger
            self.assertEqual(first[:2], replay[:2])
            self.assertEqual(len(core.observations), 2)
            for status, payload, headers in (first, replay):
                assessment = self.wire.assess_core_authz_reply_offline(
                    status, payload, headers, None, actor=actor, binding=binding,
                    plan=plan, env=self.settings, now=now)
                self.assertEqual(assessment.kind, "CURRENT_CORE_NEGATIVE")
                self.assertFalse(assessment.read_permitted)
            fresh = self.wire.prepare_core_authz_wire(
                actor, binding, env=self.settings, now=now)
            self.assertNotEqual(plan.nonce, fresh.nonce)
            foreign = ServerXref("FOREIGN", "RUN-FOREIGN-999",
                                 "INC-FOREIGN-999", "glpi-foreign", "999", "99")
            self.assertIsNone(self.wire.prepare_core_authz_wire(
                actor, foreign, env=self.settings, now=now))
            self.assertEqual(len(core.observations), 2)
            core.reply = "ALLOW"  # forged, unsigned mock; NEVER positive ACL
            forged_status, forged_payload, forged_headers = core.send(fresh)
            assessment = self.wire.assess_core_authz_reply_offline(
                forged_status, forged_payload, forged_headers, None,
                actor=actor, binding=binding, plan=fresh,
                env=self.settings, now=now)
            self.assertEqual(assessment.kind, "INVALID")
            self.assertFalse(assessment.read_permitted)
            self.assertFalse(self.wire.core_authz_read_permitted(forged_payload))
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 503)
            with self.sessions._lock:
                self.sessions._sessions.pop(self.sessions._digest(handle), None)
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 401)
            self.assert_denied(self.page.goto(
                self.base + "/runs/RUN-ACME-123"), 401)
            self.assertEqual(len(core.observations), 3,
                             "revoked session unexpectedly reached Core")
            self.assertTrue(all(x["method"] == "POST" for x in core.observations))

    def test_08_real_core_tcp_unknown_401_403_and_replay_contract(self):
        """Actual Core ASGI route on independent TLS TCP; no mock ALLOW."""
        from dataclasses import replace
        from portal.core_acl_consumer import ServerXref
        from portal_core_real_tcp_fixture import DisposableRealCoreTCP

        actor, _ = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=int(time.time()))
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        with DisposableRealCoreTCP(
                self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]) as core:
            first = core.send(plan)
            replay = core.send(plan)
            for status, payload, headers in (first, replay):
                self.assertEqual(status, 200)
                self.assertEqual(payload, {
                    "schema": "aiops.core-actor-resource-authorization.v1",
                    "decision": "UNKNOWN"})
                assessment = self.wire.assess_core_authz_reply_offline(
                    status, payload, headers, None, actor=actor, binding=binding,
                    plan=plan, env=self.settings, now=int(time.time()))
                self.assertEqual(assessment.kind, "CURRENT_CORE_NEGATIVE")
                self.assertFalse(assessment.read_permitted)
                self.assertEqual(assessment.portal_status, 503)
            # Core service authentication and tenant fence are separate from
            # OIDC identity, native GLPI human rights and resource read ACL.
            unauth = core.send(replace(plan, service_bearer="forged-" + "x" * 40))
            self.assertEqual(unauth[0], 401)
            self.assertEqual(unauth[1]["decision"], "UNKNOWN")
            self.assertEqual({k.lower(): v for k, v in unauth[2].items()}.get(
                "www-authenticate"), "Bearer")
            foreign = core.send(replace(
                plan, path=plan.path.replace("/tenants/ACME/", "/tenants/FOREIGN/")))
            self.assertEqual(foreign[0], 403)
            self.assertEqual(foreign[1]["decision"], "UNAUTHORIZED")
            self.assertEqual(len(core.observations()), 4)
            self.assertTrue(all(row["method"] == "POST" and
                                row["path"].endswith("/actor-resource-authorization")
                                for row in core.observations()))
            # A replayed nonce receives UNKNOWN; without a qualified atomic
            # ledger this is NOT proof of replay resistance or actor permission.
            self.assertFalse(self.wire.core_authz_read_permitted(first[1]))
            self.assertFalse(self.wire.core_authz_read_permitted(foreign[1]))

    def test_09_real_core_tcp_no_business_fetch_revocation_and_browser_leak(self):
        """Portal never dispatches Core/GLPI business reads on UNKNOWN."""
        from portal.core_acl_consumer import ServerXref
        from portal_core_real_tcp_fixture import DisposableRealCoreTCP

        actor, handle = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=int(time.time()))
        self.assertIsNotNone(plan)
        with DisposableRealCoreTCP(
                self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]) as core:
            self.assertEqual(core.send(plan)[0], 200)
            baseline = core.observations()
            self.assertEqual(len(baseline), 1)
            results = []
            for rid in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
                response = self.context.request.get(
                    self.base + "/api/portal/runs/" + rid,
                    headers={"Authorization": "Bearer forged",
                             "X-Actor-ID": "admin", "X-Tenant-ID": "FOREIGN",
                             "X-GLPI-Ticket": "999", "X-GLPI-Entity": "99"})
                self.assert_denied(response, 503)
                results.append(response.json())
            self.assertEqual(results[0], results[1])
            self.assertEqual(results[1], results[2])
            self.assert_denied(self.page.goto(
                self.base + "/runs/RUN-FOREIGN-999"), 503)
            # The valid OIDC session is identity-only, not native GLPI READ.
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/itsm"), 503)
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/itsm",
                headers={"Authorization": "Bearer " +
                         self.settings["AIOPS_PORTAL_READ_TOKEN"]}), 503)
            self.assertEqual(core.observations(), baseline)
            with self.sessions._lock:
                self.sessions._sessions.pop(self.sessions._digest(handle), None)
            for _ in range(2):
                self.assert_denied(self.context.request.get(
                    self.base + "/api/portal/runs/RUN-ACME-123"), 401)
                self.assert_denied(self.page.goto(
                    self.base + "/runs/RUN-ACME-123"), 401)
            self.assertEqual(core.observations(), baseline)
            foreign_actor, _ = self.session(tenant="FOREIGN")
            self.assertIsNone(self.wire.prepare_core_authz_wire(
                foreign_actor, binding, env=self.settings, now=int(time.time())))
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 503)
            self.assertEqual(core.observations(), baseline)
            for url, headers in self.observed:
                self.assertTrue(url.startswith(self.base + "/"))
                self.assertNotIn("core.example.test", url)
                for secret in (self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"],
                               self.settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"]):
                    self.assertNotIn(secret, str(headers))
            self.assertNotIn(self.settings[
                "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"], self.page.content())
            self.assertFalse(self.blocked)

    def test_10_core_negative_consumed_only_with_active_session(self):
        """Real Core TLS UNKNOWN is consumed only while OIDC session is active."""
        from fastapi import Request
        from portal.core_acl_consumer import ServerXref
        from portal_core_real_tcp_fixture import DisposableRealCoreTCP

        actor, handle = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=int(time.time()))
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)

        def server_request(cookie_handle):
            # Test-only ASGI request: identity is looked up from the server
            # store, not from X-Actor-ID or a client-provided tenant.
            cookie = (self.sessions._SESSION_COOKIE + "=" + cookie_handle).encode()
            return Request({"type": "http", "method": "GET",
                            "path": "/api/portal/runs/RUN-ACME-123",
                            "headers": [(b"cookie", cookie)]})

        with DisposableRealCoreTCP(
                self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]) as core:
            reply = core.send(plan)
            self.assertEqual(reply[0], 200)
            active = self.wire.assess_core_negative_for_session(
                server_request(handle), binding=binding, plan=plan,
                status_code=reply[0], payload=reply[1], headers=reply[2],
                env=self.settings)
            self.assertEqual(active.kind, "CURRENT_CORE_NEGATIVE")
            self.assertEqual(active.portal_status, 503)
            self.assertEqual(active.state, "UNKNOWN")
            self.assertFalse(active.read_permitted)
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 503)
            baseline = core.observations()
            self.assertEqual(len(baseline), 1)

            with self.sessions._lock:
                self.sessions._sessions.pop(self.sessions._digest(handle), None)
            for cookie_handle in (handle, "F" * 43):
                denied = self.wire.assess_core_negative_for_session(
                    server_request(cookie_handle), binding=binding, plan=plan,
                    status_code=reply[0], payload=reply[1], headers=reply[2],
                    env=self.settings)
                self.assertEqual(denied.portal_status, 401)
                self.assertFalse(denied.read_permitted)
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/RUN-ACME-123"), 401)
            self.assert_denied(self.page.goto(
                self.base + "/runs/RUN-ACME-123"), 401)
            self.assertEqual(core.observations(), baseline,
                             "revocation caused an upstream business GET")

    def test_11_core_negative_foreign_and_replay_no_business_disclosure(self):
        """Actual Core 401/403/UNKNOWN never authorizes a foreign ticket."""
        from dataclasses import replace
        from fastapi import Request
        from portal.core_acl_consumer import ServerXref
        from portal_core_real_tcp_fixture import DisposableRealCoreTCP

        actor, handle = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=int(time.time()))
        self.assertIsNotNone(plan)
        request = Request({"type": "http", "method": "GET",
                           "path": "/api/portal/runs/RUN-ACME-123",
                           "headers": [(b"cookie", (
                               self.sessions._SESSION_COOKIE + "=" + handle).encode())]})

        def assess(reply, resource=binding):
            return self.wire.assess_core_negative_for_session(
                request, binding=resource, plan=plan,
                status_code=reply[0], payload=reply[1], headers=reply[2],
                env=self.settings)

        with DisposableRealCoreTCP(
                self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]) as core:
            unknown = core.send(plan)
            replay = core.send(plan)  # Core ledger not qualified; still deny
            bad_token = core.send(replace(
                plan, service_bearer="forged-" + "x" * 40))
            foreign = core.send(replace(
                plan, path=plan.path.replace("/tenants/ACME/",
                                             "/tenants/FOREIGN/")))
            self.assertEqual([r[0] for r in (
                unknown, replay, bad_token, foreign)], [200, 200, 401, 403])
            for reply in (unknown, replay, bad_token, foreign):
                outcome = assess(reply)
                self.assertEqual(outcome.portal_status, 503)
                self.assertEqual(outcome.state, "UNKNOWN")
                self.assertFalse(outcome.read_permitted)
            forged_allow = (200, {**unknown[1], "decision": "ALLOW"}, unknown[2])
            self.assertEqual(assess(forged_allow).kind, "INVALID")
            self.assertEqual(assess(forged_allow).portal_status, 503)
            foreign_binding = ServerXref(
                "FOREIGN", "RUN-FOREIGN-999", "INC-FOREIGN-999",
                "glpi-foreign", "999", "99")
            self.assertEqual(assess(unknown, foreign_binding).kind, "INVALID")
            baseline = core.observations()
            self.assertEqual(len(baseline), 4)
            self.assertTrue(all(row["method"] == "POST" for row in baseline))
            for rid in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
                self.assert_denied(self.context.request.get(
                    self.base + "/api/portal/runs/" + rid), 503)
            self.assertEqual(core.observations(), baseline)
            self.assertFalse(any(row["method"] == "GET" for row in baseline))
            self.assertFalse(any("ticket" in str(row["path"]) for row in baseline))
            self.assertNotIn(self.settings[
                "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"], self.page.content())


    def test_12_signed_allow_claim_matrix_never_authorizes_browser_or_api(self):
        """A valid test signature and every foreign claim remain non-authoritative."""
        from fastapi import Request
        from portal.core_acl_consumer import ServerXref
        from test_portal_core_acl_consumer import PortalCoreACLConsumerTests

        actor, handle = self.session()
        binding = ServerXref("ACME", "RUN-ACME-123", "INC-ACME-123",
                             "glpi-acme", "123", "42")
        now = int(time.time())
        plan = self.wire.prepare_core_authz_wire(
            actor, binding, env=self.settings, now=now)
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        _, _, _, envelope = PortalCoreACLConsumerTests().future_envelope(now)
        envelope["request_nonce"] = plan.nonce
        public = self.key.public_key().public_numbers()

        def b64_integer(number):
            return base64.urlsafe_b64encode(number.to_bytes(
                (number.bit_length() + 7) // 8, "big")).rstrip(b"=").decode("ascii")

        settings = {**self.settings,
                    "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON": json.dumps({
                        "keys": [{"kid": "disposable-core", "kty": "RSA",
                                  "alg": "RS256", "use": "sig",
                                  "n": b64_integer(public.n),
                                  "e": b64_integer(public.e)}]})}

        def signed(body):
            value = self.key.sign(
                self.wire._canonical_signed_bytes(plan.origin, body),
                padding.PKCS1v15(), hashes.SHA256())
            return {"alg": "RS256", "kid": "disposable-core",
                    "signature": base64.urlsafe_b64encode(value).rstrip(
                        b"=").decode("ascii")}

        headers = {"cache-control": "no-store", "pragma": "no-cache",
                   "x-content-type-options": "nosniff",
                   "referrer-policy": "no-referrer"}
        cookie = (self.sessions._SESSION_COOKIE + "=" + handle).encode()
        request = Request({"type": "http", "method": "GET",
                           "path": "/api/portal/runs/RUN-ACME-123",
                           "headers": [(b"cookie", cookie)]})

        signature = signed(envelope)
        self.assertTrue(self.wire.verify_pinned_core_response_signature(
            envelope, signature, actor=actor, binding=binding, plan=plan,
            env=settings, now=now))
        # Offline signature qualification is NOT a GLPI native human ACL.
        self.assertEqual(self.wire.assess_core_authz_reply_offline(
            200, envelope, headers, signature, actor=actor, binding=binding,
            plan=plan, env=settings, now=now).kind, "SIGNED_SHAPE_UNQUALIFIED")
        self.assertEqual(self.wire.assess_core_negative_for_session(
            request, binding=binding, plan=plan, status_code=200,
            payload=envelope, headers=headers, env=settings, now=now).kind,
            "INVALID")
        self.assertFalse(self.wire.core_authz_read_permitted(envelope, signature))

        variants = (
            ("tenant", {"tenant_id": "FOREIGN"}),
            ("actor", {"actor_subject": "forged-manager"}),
            ("issuer", {"actor_issuer": "https://evil.example.test"}),
            ("audience", {"actor_audience": "evil-portal"}),
            ("run", {"run_id": "RUN-FOREIGN-999"}),
            ("incident", {"incident_id": "INC-FOREIGN-999"}),
            ("ticket", {"ticket_id": "999"}),
            ("entity", {"glpi_entity_id": "99"}),
            ("instance", {"glpi_instance_id": "glpi-foreign"}),
            ("nonce", {"request_nonce": "n" * 43}),
            ("expired", {"expires_at": now - 1}),
            ("revoked", {"revoked": True}),
            ("delegation", {"delegation": {
                **envelope["delegation"], "subject": "forged-manager"}}),
            ("native-profile", {"glpi_readback": {
                **envelope["glpi_readback"],
                "actor_permission_confirmed": False}}),
            ("native-entity", {"glpi_readback": {
                **envelope["glpi_readback"], "entity_id": "99"}}),
        )
        for label, changes in variants:
            with self.subTest(claim=label):
                altered = {**copy.deepcopy(envelope), **changes}
                # Re-sign every foreign payload: reject claim mismatch even
                # when the disposable RSA key itself is valid.
                proof = signed(altered)
                self.assertFalse(self.wire.verify_pinned_core_response_signature(
                    altered, proof, actor=actor, binding=binding, plan=plan,
                    env=settings, now=now))
                self.assertEqual(self.wire.assess_core_authz_reply_offline(
                    200, altered, headers, proof, actor=actor, binding=binding,
                    plan=plan, env=settings, now=now).kind, "INVALID")
                self.assertFalse(self.wire.core_authz_read_permitted(
                    altered, proof))

        with patch.object(self.detail, "_read_core_run",
                          side_effect=AssertionError("business Core GET forbidden")) as get_run, \
             patch.object(self.main, "get_json",
                          side_effect=AssertionError("upstream GET forbidden")) as get_json:
            api = []
            for rid in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
                response = self.context.request.get(
                    self.base + "/api/portal/runs/" + rid,
                    headers={"X-Actor-ID": "forged-manager",
                             "X-Tenant-ID": "FOREIGN",
                             "X-GLPI-Ticket": "999",
                             "X-GLPI-Entity": "99"})
                self.assert_denied(response, 503)
                api.append(response.json())
                self.assert_denied(self.page.goto(
                    self.base + "/runs/" + rid), 503)
            self.assertEqual(api[0], api[1])
            self.assertEqual(api[1], api[2])
            self.assertNotIn("ticket_id", api[0])
            get_run.assert_not_called()
            get_json.assert_not_called()

        with self.sessions._lock:
            self.sessions._sessions.pop(self.sessions._digest(handle), None)
        self.assertEqual(self.wire.assess_core_negative_for_session(
            request, binding=binding, plan=plan, status_code=200,
            payload={"schema": "aiops.core-actor-resource-authorization.v1",
                     "decision": "UNKNOWN"},
            headers=headers, env=settings, now=now).portal_status, 401)
        for rid in ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999"):
            self.assert_denied(self.context.request.get(
                self.base + "/api/portal/runs/" + rid), 401)
            self.assert_denied(self.page.goto(self.base + "/runs/" + rid), 401)
        for url, request_headers in self.observed:
            self.assertTrue(url.startswith(self.base + "/"))
            self.assertNotIn("core.example.test", url)
            for token in (self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"],
                          self.settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"]):
                self.assertNotIn(token, str(request_headers))
                self.assertNotIn(token, self.page.content())
        self.assertFalse(self.blocked)
