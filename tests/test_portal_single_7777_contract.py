"""Single canonical Portal 7777 contract; disposable HTTP, no host inspection.

This suite does not prove Debian PortBindings, GLPI human ACL or Core ALLOW.
It runs in the existing ephemeral Quality browser job without a second stack.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-internal-" + "i" * 40}):
    from portal import main, oidc_session, acme_run_detail
from portal.oidc_identity import IdentityUnavailable, PortalActorContext

HANDLE = "P" * 43
VIEWER = "viewer-" + "v" * 40
SERVICE = "service-" + "s" * 40
ORIGIN = "https://portal.example.test:7777"
CONFIG = {
    "AIOPS_PORTAL_OIDC_ISSUER": "https://idp.example.test/realms/acme",
    "AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT": "https://idp.example.test/authorize",
    "AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT": "https://idp.example.test/token",
    "AIOPS_PORTAL_OIDC_CLIENT_ID": "aiops2-portal",
    "AIOPS_PORTAL_OIDC_AUDIENCE": "aiops2-portal",
    "AIOPS_PORTAL_OIDC_REDIRECT_URI": ORIGIN + "/auth/oidc/callback",
    "AIOPS_PORTAL_READ_TOKEN": VIEWER,
    "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": SERVICE,
}


class PortalSingle7777NegativeContract(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, CONFIG)
        self.environment.start()
        self.client = TestClient(main.app, base_url=ORIGIN)
        with oidc_session._lock:
            oidc_session._sessions.clear()
            oidc_session._pending.clear()

    def tearDown(self):
        self.client.close()
        with oidc_session._lock:
            oidc_session._sessions.clear()
            oidc_session._pending.clear()
        self.environment.stop()

    def _session(self):
        actor = PortalActorContext(
            "operator-123", "ACME", ("N2",),
            CONFIG["AIOPS_PORTAL_OIDC_ISSUER"], "aiops2-portal",
            expires_at=int(time.time()) + 300,
        )
        with oidc_session._lock:
            oidc_session._sessions[oidc_session._digest(HANDLE)] = (
                oidc_session._Session(actor, int(time.time()) + 300))
        self.client.cookies.set(oidc_session._SESSION_COOKIE, HANDLE,
                                domain="portal.example.test", path="/")

    def _fence(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        self.assertNotIn(SERVICE, response.text)
        self.assertNotIn("CONNECTED", response.text)

    def test_health_reports_intent_not_host_port_binding(self):
        for raw, expected in (
            ("", "UNCONFIGURED"),
            ("7777", "CONFIGURED_UNVERIFIED"),
            ("17777", "MISMATCH_UNVERIFIED"),
            ("7778", "MISMATCH_UNVERIFIED"),
        ):
            with self.subTest(raw=raw), patch.dict(
                    os.environ, {"AIOPS_PORTAL_HOST_PORT": raw}):
                response = self.client.get("/health")
                self._fence(response, 200)
                data = response.json()
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["canonical_host_port"], 7777)
                self.assertEqual(data["host_port_binding_state"], expected)
                self.assertIs(data["host_port_binding_verified"], False)
                self.assertEqual(data["runtime_exposure"], "UNKNOWN")
                self.assertNotIn("external_port", data)
                self.assertNotIn("17777", response.text)

    def test_oidc_redirect_and_logout_pin_7777_not_17777(self):
        config = oidc_session._config()
        self.assertEqual(config.origin, ORIGIN)
        self.assertEqual(config.redirect, ORIGIN + "/auth/oidc/callback")
        login = self.client.get("/auth/oidc/login", follow_redirects=False)
        self.assertEqual(login.status_code, 303)
        self.assertIn("redirect_uri=https%3A%2F%2Fportal.example.test%3A7777",
                      login.headers["location"])
        self.assertEqual(login.headers["cache-control"], "no-store")
        self.assertIn("Secure", login.headers["set-cookie"])
        self.assertIn("HttpOnly", login.headers["set-cookie"])
        for bad in (
            "https://portal.example.test:17777/auth/oidc/callback",
            "https://portal.example.test:7778/auth/oidc/callback",
            "http://portal.example.test:7777/auth/oidc/callback",
        ):
            with self.subTest(redirect=bad), patch.dict(
                    os.environ, {"AIOPS_PORTAL_OIDC_REDIRECT_URI": bad}):
                with self.assertRaises(IdentityUnavailable):
                    oidc_session._config()
        with patch.dict(os.environ, {
            "AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT": "https://idp.example.test:7777/token"
        }):
            with self.assertRaises(IdentityUnavailable):
                oidc_session._config()

    def test_single_entry_revocation_and_non_enumeration_without_upstream(self):
        self._session()
        with (
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("network upstream forbidden")) as network,
            patch.object(main, "get_json",
                         side_effect=AssertionError("Core/GLPI GET forbidden")) as core,
            patch.object(main, "post_json",
                         side_effect=AssertionError("Core/GLPI POST forbidden")) as post,
            patch.object(acme_run_detail, "_read_core_run",
                         side_effect=AssertionError("Run GET forbidden")) as run,
        ):
            projections = []
            for rid in ("RUN-ACME-123", "RUN-FOREIGN-999",
                        "RUN-NOT-FOUND", "RUN-forged!"):
                response = self.client.get("/api/portal/runs/" + rid, headers={
                    "Authorization": "Bearer " + VIEWER,
                    "X-Actor-ID": "admin", "X-Tenant-ID": "FOREIGN",
                    "X-GLPI-Profile": "manager",
                })
                self._fence(response, 503)
                projections.append(response.json())
                self.assertNotIn("ticket_id", response.text)
            self.assertTrue(all(p == projections[0] for p in projections))
            for route, method in (
                ("/api/portal/itsm", "get"),
                ("/api/noc/runtime-state", "get"),
                ("/api/noc/correlation", "get"),
                ("/api/portal/bootstrap", "get"),
                ("/api/copilot", "post"),
            ):
                response = getattr(self.client, method)(
                    route, headers={"Authorization": "Bearer " + VIEWER})
                self._fence(response, 503)
            wrong_origin = self.client.post("/auth/oidc/logout",
                                            headers={"Origin": "https://portal.example.test:17777"})
            self._fence(wrong_origin, 403)
            self._fence(self.client.get("/api/portal/session"), 503)
            revoked = self.client.post("/auth/oidc/logout",
                                       headers={"Origin": ORIGIN})
            self.assertEqual(revoked.status_code, 204)
            self.assertEqual(revoked.headers["cache-control"], "no-store")
            self._fence(self.client.get("/api/portal/session"), 401)
            network.assert_not_called()
            core.assert_not_called()
            post.assert_not_called()
            run.assert_not_called()
        self._receipt({
            "canonical_port": 7777,
            "legacy_port_rejected_as_logout_origin": True,
            "oidc_revoked_http": 401,
            "run_variants_indistinguishable": len(projections),
            "business_get_count": 0,
            "browser_service_bearer_exposed": False,
        })

    def _receipt(self, observations):
        destination = os.environ.get("AIOPS_E2E_ARTIFACT_DIR")
        if not destination:
            return
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        payload = {
            "schema": "aiops.portal.single-entry-negative.v1",
            "source_head": head,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "canonical_host_port_expected": 7777,
            "debian_port_binding_observed": False,
            "host_port_binding_state": "UNKNOWN",
            "glpi_native_human_rights": "NOT_ATTESTED",
            "idp_glpi_independent_mapping": "NOT_ATTESTED",
            "core_signer_and_atomic_nonce_jti": "NOT_ATTESTED",
            "dispatch_allowed": False, "read_permitted": False,
            "positive_allow_tested": False,
            "observations": observations,
            "result": "NEGATIVE_CONTRACT_PASS",
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(raw).hexdigest()
        output = Path(destination)
        output.mkdir(parents=True, exist_ok=True)
        (output / "portal-single-7777-negative.json").write_text(
            json.dumps({"receipt": payload, "sha256": digest},
                       sort_keys=True, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
