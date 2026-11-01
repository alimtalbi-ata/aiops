"""Portal-only negative Host/OIDC cookie contract; no Debian or GLPI access.

Disposable TestClient HTTPS Host simulation is NOT proof of host PortBindings.
All identities, tokens and Run identifiers below are synthetic.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-" + "i" * 48}):
    from portal import acme_run_detail, main, oidc_session
    from portal.oidc_identity import PortalActorContext

VIEWER = "ci-viewer-" + "v" * 40
SERVICE = "ci-core-service-" + "s" * 40
COOKIE = oidc_session._SESSION_COOKIE
RUNS = ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999")


def receipt(case: str, observed: dict) -> None:
    directory = os.getenv("AIOPS_E2E_ARTIFACT_DIR", "")
    if not directory:
        return
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=3).strip()
    except (OSError, subprocess.SubprocessError):
        sha = "NOT_AVAILABLE"
    payload = {
        "schema": "aiops.portal-host-cookie-negative-receipt.v1",
        "case": case,
        "source_sha": sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
        "result": "NEGATIVE_PASS",
        "canonical_host_port_desired": 7777,
        "alias_17777_is_canonical": False,
        "host_port_binding_verified": False,
        "runtime_exposure": "UNKNOWN",
        "idp_glpi_native_rights_attested": False,
        "core_signer_and_durable_nonce_attested": False,
        "positive_read_enabled": False,
        "dispatch_allowed": False,
        "observed": observed,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["canonical_sha256"] = hashlib.sha256(encoded).hexdigest()
    (root / ("portal-host-cookie-" + case + ".json")).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class PortalHostCookieNegativeContract(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "AIOPS_INTERNAL_TOKEN": "ci-" + "i" * 48,
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
            "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": SERVICE,
            "AIOPS_PORTAL_OIDC_ISSUER": "https://idp.example.test/realms/acme",
            "AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT":
                "https://idp.example.test/realms/acme/protocol/openid-connect/auth",
            "AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT":
                "https://idp.example.test/realms/acme/protocol/openid-connect/token",
            "AIOPS_PORTAL_OIDC_CLIENT_ID": "aiops2-portal",
            "AIOPS_PORTAL_OIDC_AUDIENCE": "aiops2-portal",
            "AIOPS_PORTAL_OIDC_REDIRECT_URI":
                "https://portal.example.test/auth/oidc/callback",
        }
        self.env = patch.dict(os.environ, self.settings)
        self.env.start()
        with oidc_session._lock:
            oidc_session._pending.clear()
            oidc_session._sessions.clear()
        self.client = TestClient(main.app,
                                 base_url="https://portal.example.test:7777",
                                 follow_redirects=False)

    def tearDown(self):
        self.client.close()
        with oidc_session._lock:
            oidc_session._pending.clear()
            oidc_session._sessions.clear()
        self.env.stop()

    def _headers(self, handle: str | None = None) -> dict:
        result = {
            "Authorization": "Bearer " + VIEWER,
            "X-Actor-ID": "forged-manager",
            "X-Tenant-ID": "FOREIGN",
            "X-GLPI-Entity": "99",
            "X-GLPI-Ticket": "999",
        }
        if handle is not None:
            result["Cookie"] = COOKIE + "=" + handle
        return result

    def _session(self) -> str:
        handle = "A" * 43
        now = int(time.time())
        actor = PortalActorContext(
            "operator-123", "ACME", ("N2",),
            "https://idp.example.test/realms/acme", "aiops2-portal",
            expires_at=now + 600)
        with oidc_session._lock:
            oidc_session._sessions[oidc_session._digest(handle)] = (
                oidc_session._Session(actor, now + 600))
        return handle

    def _assert_protected(self, response, expected: int) -> None:
        self.assertEqual(response.status_code, expected)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        self.assertNotIn(SERVICE, response.text)
        self.assertNotIn(VIEWER, response.text)
        self.assertNotIn("tenant_acl_qualified\": true", response.text.lower())

    def test_01_forged_and_revoked_oidc_cookie_cannot_downgrade_to_viewer(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("business GET")) as get, \
             patch.object(main, "post_json",
                          side_effect=AssertionError("business POST")) as post:
            forged = "Z" * 43
            for rid in RUNS:
                for prefix in ("/api/portal/runs/", "/runs/"):
                    self._assert_protected(self.client.get(
                        prefix + rid, headers=self._headers(forged)), 401)
            handle = self._session()
            self._assert_protected(self.client.get(
                "/api/portal/runs/" + RUNS[0], headers=self._headers(handle)), 503)
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(handle), None)
            for rid in RUNS:
                for prefix in ("/api/portal/runs/", "/runs/"):
                    self._assert_protected(self.client.get(
                        prefix + rid, headers=self._headers(handle)), 401)
            core.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()
        receipt("revoked-cookie", {"forged": 401, "valid_identity_only": 503,
                                   "revoked": 401, "run_variants": len(RUNS)})

    def test_02_valid_oidc_session_never_enumerates_tenant_runs_or_tickets(self):
        handle = self._session()
        projections = []
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("business GET")) as get:
            for rid in RUNS:
                response = self.client.get("/api/portal/runs/" + rid,
                                           headers=self._headers(handle))
                self._assert_protected(response, 503)
                projections.append(response.json())
                html = self.client.get("/runs/" + rid,
                                       headers=self._headers(handle))
                self._assert_protected(html, 503)
                self.assertIn("NOT VERIFIED", html.text)
                self.assertNotIn("Tenant-authorized Run:", html.text)
            self.assertEqual(projections[0], projections[1])
            self.assertEqual(projections[1], projections[2])
            self.assertNotIn("ticket_id", projections[0])
            self.assertNotIn("run_id", projections[0])
            core.assert_not_called()
            get.assert_not_called()
        receipt("no-enumeration", {"status": 503,
                                    "equal_api_projections": True,
                                    "run_variants": len(RUNS)})

    def test_03_7777_origin_is_not_acl_and_17777_is_not_substitute(self):
        # Simulated HTTPS Host header does not attest a real Debian listener.
        good = self.client.post(
            "/api/portal/run-session",
            headers={**self._headers(), "Origin": "https://portal.example.test:7777",
                     "X-Portal-Run-ID": RUNS[0]})
        self._assert_protected(good, 503)
        for origin in ("https://portal.example.test:17777",
                       "http://portal.example.test:7777",
                       "https://foreign.example.test:7777"):
            with self.subTest(origin=origin):
                response = self.client.post(
                    "/api/portal/run-session",
                    headers={**self._headers(), "Origin": origin,
                             "X-Portal-Run-ID": RUNS[0]})
                self._assert_protected(response, 403)
                self.assertNotIn("set-cookie", response.headers)
        with patch.dict(os.environ, {
            "AIOPS_PORTAL_OIDC_REDIRECT_URI":
                "https://portal.example.test:17777/auth/oidc/callback"
        }):
            response = self.client.get("/auth/oidc/login")
            self._assert_protected(response, 503)
            self.assertNotIn("location", response.headers)
        receipt("host-origin", {"same_origin_identity_only": 503,
                                "foreign_or_alias_origin": 403,
                                "oidc_alias_redirect": 503})


    def test_04_duplicate_oidc_cookie_never_selects_a_valid_handle(self):
        # Starlette's parsed cookie dict would otherwise keep the last value.
        # A forged+valid pair is not a legitimate OIDC session, in either order.
        valid = self._session()
        forged = "Z" * 43
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("business GET")) as get:
            for first, second in ((valid, forged), (forged, valid),
                                  (valid, valid)):
                for rid in RUNS:
                    for prefix in ("/api/portal/runs/", "/runs/"):
                        with self.subTest(order=(first == valid, second == valid),
                                          rid=rid, route=prefix):
                            headers = self._headers()
                            headers["Cookie"] = (
                                COOKIE + "=" + first + "; " + COOKIE + "=" + second)
                            self._assert_protected(
                                self.client.get(prefix + rid, headers=headers), 401)
            core.assert_not_called()
            get.assert_not_called()
        receipt("duplicate-oidc-cookie", {
            "status": 401, "cookie_orders": 3, "run_variants": len(RUNS),
            "api_html_identical_status": True, "upstream_business_get": 0,
        })

    def test_05_http_request_cannot_borrow_https_origin_or_proxy_headers(self):
        # Simulate the ASGI request scheme, not a Debian TLS/port probe.
        headers = {
            **self._headers(),
            "Origin": "https://portal.example.test:7777",
            "X-Portal-Run-ID": RUNS[0],
            "X-Forwarded-Proto": "https",
            "Forwarded": "proto=https;host=portal.example.test:7777",
        }
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("business GET")) as get, \
             patch.object(main, "post_json",
                          side_effect=AssertionError("business POST")) as post:
            downgraded = self.client.post(
                "http://portal.example.test:7777/api/portal/run-session",
                headers=headers)
            self._assert_protected(downgraded, 403)
            self.assertNotIn("set-cookie", downgraded.headers)
            # Matching HTTPS Host/Origin is still identity-only, not GLPI READ.
            same_origin = self.client.post(
                "/api/portal/run-session", headers=headers)
            self._assert_protected(same_origin, 503)
            self.assertFalse(same_origin.json()["tenant_acl_qualified"])
            alias = self.client.post(
                "/api/portal/run-session",
                headers={**headers, "Origin": "https://portal.example.test:17777"})
            self._assert_protected(alias, 403)
            core.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()
        receipt("http-origin-downgrade", {
            "http_request_https_origin": 403,
            "https_7777_identity_only": 503,
            "https_17777_alias": 403,
            "forwarded_headers_authoritative": False,
            "upstream_business_requests": 0,
        })



if __name__ == "__main__":
    unittest.main()
