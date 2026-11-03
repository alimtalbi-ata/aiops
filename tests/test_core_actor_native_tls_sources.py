"""Real TLS (not an HTTP bridge) for three independent disposable human authorities.

The CA and all private keys are generated at test time and deleted. Each source
has its own TLS listener/certificate on 127/8. The test pins only that ephemeral
CA as the requests trust anchor; requests keeps verify=True, CERT_REQUIRED,
hostname/IP-SAN verification, and redirects disabled. No real IdP/GLPI or ALLOW.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import requests
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from core import actor_native_authority as native
from core import actor_resource_authz as actor
from test_core_actor_disposable_sources import (
    AuthorityHandler, CONFIG, EXPECTED, IDP, ISSUER,
)

PORT = 8443
IPS = {"idp": "127.0.0.2", "mapping": "127.0.0.3", "glpi": "127.0.0.4"}


class DisposableNativeTLSAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not shutil.which("openssl"):
            raise RuntimeError("OpenSSL required: native TLS authority gate cannot be skipped")
        cls.temp = tempfile.TemporaryDirectory(prefix="aiops-native-tls-")
        cls.root = Path(cls.temp.name)

        def openssl(*args):
            subprocess.run(["openssl", *map(str, args)], check=True, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
                "-days", "1", "-subj", "/CN=AIOps disposable actor CA",
                "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                "-keyout", cls.root / "ca.key", "-out", cls.root / "ca.pem")
        for role, ip in {**IPS, "wrong_mapping": "127.0.0.99"}.items():
            openssl("req", "-newkey", "rsa:2048", "-nodes",
                    "-subj", "/CN=disposable-" + role,
                    "-keyout", cls.root / (role + ".key"),
                    "-out", cls.root / (role + ".csr"))
            ext = cls.root / (role + ".ext")
            ext.write_text("subjectAltName=IP:" + ip +
                           "\nextendedKeyUsage=serverAuth\n"
                           "keyUsage=digitalSignature,keyEncipherment\n",
                           encoding="ascii")
            openssl("x509", "-req", "-in", cls.root / (role + ".csr"),
                    "-CA", cls.root / "ca.pem", "-CAkey", cls.root / "ca.key",
                    "-CAcreateserial", "-out", cls.root / (role + ".pem"),
                    "-days", "1", "-sha256", "-extfile", ext)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.now = int(time.time())
        self.claims = dict(
            active=True, revoked=False, iss=ISSUER, aud=IDP["audience"],
            sub="idp|alice", iat=self.now-10, nbf=self.now-5,
            exp=self.now+120, jti="JTI_disposable_0000000000000001",
            glpi_user_id=47, permissions=["run:read"], **EXPECTED)
        self.servers = {}
        try:
            for role, ip in IPS.items():
                server = ThreadingHTTPServer((ip, PORT), AuthorityHandler)
                server.daemon_threads = True
                server.role, server.calls, server.now = role, [], self.now
                server.claims, server.revoked = self.claims, False
                server.ticket_right, server.entity = 1, 7
                leaf = ("wrong_mapping" if role == "mapping" and
                        self._testMethodName == "test_hostname_mismatch_is_rejected"
                        else role)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(
                    str(self.root / (leaf + ".pem")),
                    str(self.root / (leaf + ".key")))
                server.socket = context.wrap_socket(server.socket, server_side=True)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                self.servers[role] = (server, thread)

            cfg = {**CONFIG,
                   "mapping_url": "https://" + IPS["mapping"] + ":8443/map",
                   "glpi_origin": "https://" + IPS["glpi"] + ":8443"}
            idp = {**IDP,
                   "url": "https://" + IPS["idp"] + ":8443/introspect"}
            self.env = patch.dict(os.environ, {
                "AIOPS_XREF_ACTOR_INTROSPECTION_JSON": json.dumps(idp),
                "AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": json.dumps([cfg]),
            })
            self.env.start()
            # Trust an ephemeral CA; do not replace requests.Session or its
            # HTTPAdapter, disable certificate checks, or rewrite HTTPS to HTTP.
            self.trust = patch("requests.adapters.DEFAULT_CA_BUNDLE_PATH",
                               str(self.root / "ca.pem"))
            self.trust.start()
            # requests 2.32.4 preloads an SSLContext at import time, before
            # DEFAULT_CA_BUNDLE_PATH can be patched. Replace only its trust
            # anchor with a new CERT_REQUIRED, hostname-checking context.
            ca_context = ssl.create_default_context(cafile=str(self.root / "ca.pem"))
            self.preloaded_trust = patch.object(
                requests.adapters, "_preloaded_ssl_context",
                ca_context, create=True)
            self.preloaded_trust.start()
        except Exception:
            self.tearDown()
            raise

    def tearDown(self):
        if hasattr(self, "preloaded_trust"):
            self.preloaded_trust.stop()
            del self.preloaded_trust
        if hasattr(self, "trust"):
            self.trust.stop()
            del self.trust
        if hasattr(self, "env"):
            self.env.stop()
            del self.env
        for server, thread in self.servers.values():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.servers.clear()

    def preflight(self, expected=None):
        expected = expected or EXPECTED
        claims = actor._actor_introspection(
            "opaque-delegation-disposable-token", expected, self.now)
        return claims, (native._native_glpi_preflight(claims, expected, self.now)
                        if claims is not None else False)

    def calls(self, role):
        return len(self.servers[role][0].calls)

    def test_three_verified_tls_sources_still_never_allow(self):
        # Exercise the genuine TLS adapter before the OAuth introspection.
        with requests.Session() as session:
            session.trust_env = False
            try:
                response = session.get(
                    "https://127.0.0.2:8443/introspect", verify=True,
                    allow_redirects=False, timeout=(2, 3))
            except requests.RequestException as exc:
                self.fail("Real TLS handshake failed: " + repr(exc)[:500])
            self.assertEqual(response.status_code, 401)
        self.servers["idp"][0].calls.clear()
        claims, passed = self.preflight()
        self.assertIsNotNone(claims)
        self.assertTrue(passed)
        self.assertEqual([self.calls(k) for k in IPS], [1, 1, 5])
        self.assertEqual(actor._reply().status_code, 200)
        self.assertEqual(json.loads(actor._reply().body)["decision"], "UNKNOWN")

    def test_wrong_issuer_rejected_before_human_sources(self):
        self.servers["idp"][0].claims = {**self.claims, "iss": "https://other.invalid"}
        self.assertFalse(self.preflight()[1])
        self.assertEqual(self.calls("mapping"), 0)
        self.assertEqual(self.calls("glpi"), 0)

    def test_foreign_tenant_and_run_are_not_enumerated(self):
        for changes in ({"tenant_id": "TEN-B"}, {"run_id": "RUN-FOREIGN"}):
            with self.subTest(changes=changes):
                self.assertFalse(self.preflight({**EXPECTED, **changes})[1])
                self.assertEqual(self.calls("mapping"), 0)
                self.assertEqual(self.calls("glpi"), 0)

    def test_actor_subject_to_glpi_user_mismatch_rejected(self):
        self.servers["idp"][0].claims = {**self.claims, "glpi_user_id": 48}
        self.assertFalse(self.preflight()[1])
        self.assertEqual(self.calls("glpi"), 1)  # getFullSession rejects wrong actor

    def test_native_ticket_read_bit_required(self):
        self.servers["glpi"][0].ticket_right = 0
        self.assertFalse(self.preflight()[1])

    def test_exact_ticket_entity_required(self):
        self.servers["glpi"][0].entity = 8
        self.assertFalse(self.preflight()[1])

    def test_mapping_revocation_rejected_before_glpi(self):
        self.servers["mapping"][0].revoked = True
        self.assertFalse(self.preflight()[1])
        self.assertEqual(self.calls("glpi"), 0)

    def test_untrusted_ca_fails_closed_without_http_bridge(self):
        # A genuine TLS trust failure; no HTTP handler should receive a request.
        with patch("requests.adapters.DEFAULT_CA_BUNDLE_PATH", requests.certs.where()), \
             patch.object(requests.adapters, "_preloaded_ssl_context",
                          ssl.create_default_context(cafile=requests.certs.where()),
                          create=True):
            self.assertFalse(self.preflight()[1])
        self.assertEqual(self.calls("idp"), 0)
        self.assertEqual(self.calls("mapping"), 0)

    def test_hostname_mismatch_is_rejected(self):
        # Mapping server presents a CA-signed leaf for 127.0.0.99, not .3.
        self.assertFalse(self.preflight()[1])
        self.assertEqual(self.calls("idp"), 1)
        self.assertEqual(self.calls("mapping"), 0)
        self.assertEqual(self.calls("glpi"), 0)


if __name__ == "__main__":
    unittest.main()
