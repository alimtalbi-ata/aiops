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


    def test_06_split_cookie_fields_never_downgrade_to_viewer_or_glpi_rights(self):
        # HTTP permits repeated Cookie fields in some intermediaries; Starlette
        # request.cookies can see only one. Every raw field is inspected.
        valid = self._session()
        forged = "Z" * 43
        cases = (
            (COOKIE + "=" + valid, COOKIE + "=" + forged),
            (COOKIE + "=" + forged, COOKIE + "=" + valid),
            (COOKIE + "=" + valid, COOKIE + "=" + valid),
            ("unrelated=1", COOKIE + "=" + forged),
            ("unrelated=1", COOKIE + "=" + valid),
            (COOKIE + "=" + valid, "unrelated=1"),
        )
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("GLPI/Core business GET")) as get, \
             patch.object(main, "post_json",
                          side_effect=AssertionError("business POST")) as post:
            for first, second in cases:
                # Sequence preserves two distinct raw Cookie headers.
                headers = [
                    ("Authorization", "Bearer " + VIEWER),
                    ("X-Actor-ID", "forged-manager"),
                    ("X-Tenant-ID", "FOREIGN"),
                    ("X-GLPI-Profile", "Super-Admin"),
                    ("X-GLPI-Entity", "99"),
                    ("Cookie", first), ("Cookie", second),
                ]
                for rid in RUNS:
                    for prefix in ("/api/portal/runs/", "/runs/"):
                        with self.subTest(cookie_fields=cases.index((first, second)),
                                          run=rid, route=prefix):
                            response = self.client.get(prefix + rid, headers=headers)
                            self._assert_protected(response, 401)
                            self.assertNotIn("set-cookie", response.headers)
            # Even a single valid identity cookie and spoofed native GLPI
            # profile/entity claims cannot establish independent human rights.
            projections = []
            for rid in RUNS:
                response = self.client.get("/api/portal/runs/" + rid, headers={
                    **self._headers(valid),
                    "X-GLPI-Profile": "Super-Admin",
                    "X-GLPI-Permission": "READ",
                })
                self._assert_protected(response, 503)
                projections.append(response.json())
            self.assertEqual(projections[0], projections[1])
            self.assertEqual(projections[1], projections[2])
            self.assertEqual(projections[0]["journey"]["GLPI"]["state"], "UNKNOWN")
            self.assertFalse(projections[0]["tenant_acl_qualified"])
            core.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()
        receipt("split-cookie-fields", {
            "duplicate_or_split_cookie_cases": len(cases),
            "run_variants": len(RUNS),
            "routes_per_variant": 2,
            "explicit_cookie_status": 401,
            "identity_only_glpi_human_rights": "UNKNOWN",
            "identity_only_http_status": 503,
            "upstream_business_requests": 0,
        })

    def test_07_callback_redirect_pins_https_7777_not_17777(self):
        from urllib.parse import parse_qs, urlsplit

        callback = "https://portal.example.test:7777/auth/oidc/callback"
        with patch.dict(os.environ, {"AIOPS_PORTAL_OIDC_REDIRECT_URI": callback}):
            # Login is a local redirect builder; no IdP token exchange or
            # external network request, and no host PortBindings attestation.
            response = self.client.get("/auth/oidc/login")
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(parse_qs(urlsplit(response.headers["location"]).query)[
                "redirect_uri"], [callback])
            self.assertIn("Secure", response.headers["set-cookie"])
            self.assertIn("HttpOnly", response.headers["set-cookie"])
            self.assertNotIn(VIEWER, response.headers["location"])
            self.assertNotIn(SERVICE, response.headers["location"])
            state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
            state_cookie = response.headers["set-cookie"].split(";", 1)[0]
            # Cookies are not port-scoped. Even a copied secure state cookie
            # cannot authorize a callback on :17777 or an HTTP downgrade.
            with patch.object(oidc_session, "_exchange",
                              side_effect=AssertionError("IdP exchange")) as exchange:
                for wrong_url in (
                    "https://portal.example.test:17777/auth/oidc/callback",
                    "http://portal.example.test:7777/auth/oidc/callback",
                ):
                    with self.subTest(callback=wrong_url):
                        wrong = self.client.get(
                            wrong_url, params={"code": "fixture", "state": state},
                            headers={"Cookie": state_cookie})
                        self.assertEqual(wrong.status_code, 401)
                        self.assertEqual(wrong.json()["state"], "UNKNOWN")
                        self.assertNotIn("set-cookie", wrong.headers)
                exchange.assert_not_called()
        for rejected in (
            "https://portal.example.test:17777/auth/oidc/callback",
            "https://portal.example.test:8443/auth/oidc/callback",
            "http://portal.example.test:7777/auth/oidc/callback",
        ):
            with self.subTest(redirect=rejected), patch.dict(
                    os.environ, {"AIOPS_PORTAL_OIDC_REDIRECT_URI": rejected}):
                response = self.client.get("/auth/oidc/login")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["state"], "UNKNOWN")
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertNotIn("location", response.headers)
                self.assertNotIn("set-cookie", response.headers)
        receipt("callback-7777-only", {
            "https_7777_redirect": 303,
            "https_17777_redirect": 503,
            "https_other_port_redirect": 503,
            "http_7777_redirect": 503,
            "https_17777_callback": 401,
            "http_7777_callback": 401,
            "host_port_binding_verified": False,
            "real_idp_or_glpi_attested": False,
        })



    def test_08_unattested_independent_human_authority_cannot_be_browser_supplied(self):
        """IdP subject is identity; native GLPI and Core resource proofs are absent.

        Deliberately no synthetic ALLOW. A forged set of *all* source claims
        must not turn a viewer or OIDC session into GLPI ticket READ.
        """
        from portal import core_authz_transport

        valid = self._session()
        forged_authority = {
            "X-GLPI-User-ID": "77",
            "X-GLPI-Profile": "Super-Admin",
            "X-GLPI-Entity": "42",
            "X-GLPI-Ticket": "123",
            "X-GLPI-Permission": "READ",
            "X-GLPI-READMY": "1",
            "X-Core-Run-ID": RUNS[0],
            "X-Core-Incident-ID": "INC-ACME-123",
            "X-Core-Signed-Decision": "ALLOW",
            "X-Core-Nonce": "browser-forged-nonce",
            "X-Actor-ID": "operator-123",
            "X-Tenant-ID": "ACME",
        }
        self.assertFalse(core_authz_transport.core_authz_read_permitted())
        projections = []
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("GLPI/Core GET")) as get, \
             patch.object(main, "post_json",
                          side_effect=AssertionError("business POST")) as post:
            for rid in RUNS:
                for prefix in ("/api/portal/runs/", "/runs/"):
                    response = self.client.get(prefix + rid, headers={
                        **self._headers(valid), **forged_authority})
                    self._assert_protected(response, 503)
                    if prefix.startswith("/api/"):
                        projections.append(response.json())
                        self.assertEqual(response.json()["journey"]["GLPI"]["state"],
                                         "UNKNOWN")
                        self.assertFalse(response.json()["tenant_acl_qualified"])
                    self.assertNotIn("set-cookie", response.headers)
            self.assertEqual(projections[0], projections[1])
            self.assertEqual(projections[1], projections[2])
            # A foreign tenant is not a proof of access to an ACME Run.
            now = int(time.time())
            foreign = PortalActorContext(
                "operator-123", "FOREIGN", ("N2",),
                "https://idp.example.test/realms/acme", "aiops2-portal",
                expires_at=now + 600)
            with oidc_session._lock:
                oidc_session._sessions[oidc_session._digest(valid)] = (
                    oidc_session._Session(foreign, now + 600))
            foreign_response = self.client.get(
                "/api/portal/runs/" + RUNS[0],
                headers={**self._headers(valid), **forged_authority})
            self._assert_protected(foreign_response, 503)
            self.assertEqual(foreign_response.json(), projections[0])
            # Explicit revocation wins over a valid viewer bearer and
            # forged native rights, without querying ticket existence.
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(valid), None)
            for rid in RUNS:
                response = self.client.get("/api/portal/runs/" + rid,
                                           headers={**self._headers(valid),
                                                    **forged_authority})
                self._assert_protected(response, 401)
            same_origin = self.client.post("/api/portal/run-session", headers={
                **self._headers(), **forged_authority,
                "Origin": "https://portal.example.test:7777",
                "X-Portal-Run-ID": RUNS[0]})
            self._assert_protected(same_origin, 503)
            alias = self.client.post("/api/portal/run-session", headers={
                **self._headers(), **forged_authority,
                "Origin": "https://portal.example.test:17777",
                "X-Portal-Run-ID": RUNS[0]})
            self._assert_protected(alias, 403)
            core.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()
        receipt("independent-human-authority-unattested", {
            "valid_oidc_without_native_glpi_rights": 503,
            "foreign_tenant_without_core_binding": 503,
            "revoked_oidc_with_forged_glpi_rights": 401,
            "https_7777_origin_without_acl": 503,
            "https_17777_origin_alias": 403,
            "run_variants": len(RUNS),
            "upstream_business_requests": 0,
            "missing_independent_proofs": [
                "idp_subject_to_glpi_user_source_binding",
                "native_glpi_user_profile_entity_ticket_read",
                "core_actor_tenant_run_incident_ticket_binding",
                "core_signer_rotation_and_revocation",
                "durable_atomic_nonce_jti_revocation",
                "debian_7777_portbindings_host_tls",
            ],
            "synthetic_positive_allow": False,
        })


    def test_09_glpi_native_readmy_unknown_oidc_cookie_never_downgrades(self):
        """Operator-visible GLPI gate: no native READMY/READ or Core authority."""
        handle = self._session()
        forged = "Z" * 43
        claims = {
            "X-GLPI-User-ID": "77", "X-GLPI-Profile": "Super-Admin",
            "X-GLPI-Entity": "42", "X-GLPI-Ticket": "123",
            "X-GLPI-Permission": "READ", "X-GLPI-READMY": "1",
            "X-Core-Signed-Decision": "ALLOW", "X-Core-Run-ID": RUNS[0],
            "X-Tenant-ID": "ACME", "X-Actor-ID": "operator-123",
        }
        projections = []
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business GET")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("business GET")) as get, \
             patch.object(main, "post_json",
                          side_effect=AssertionError("business POST")) as post:
            # Explicit OIDC wins over viewer bearer, regardless of forged rights.
            self._assert_protected(self.client.get(
                "/api/portal/itsm", headers={**self._headers(forged), **claims}), 401)
            for rid in RUNS:
                response = self.client.get("/api/portal/itsm", headers={
                    **self._headers(handle), **claims, "X-Core-Run-ID": rid})
                self._assert_protected(response, 503)
                body = response.json()
                projections.append(body)
                self.assertEqual(body["state"], "UNKNOWN")
                self.assertFalse(body["human_authority"]["human_allow"])
                self.assertEqual(body["human_authority"]["readmy_ticket_ownership"],
                                 "UNKNOWN")
                self.assertEqual(body["human_authority"][
                    "native_user_profile_entity_ticket_read"], "UNKNOWN")
                self.assertFalse(body["glpi_write_enabled"])
            self.assertEqual(projections[0], projections[1])
            self.assertEqual(projections[1], projections[2])
            # Valid identity without viewer is not GLPI human authority.
            self._assert_protected(self.client.get(
                "/api/portal/itsm", headers={"Cookie": COOKIE + "=" + handle}), 503)
            # Duplicate/split Cookie headers cannot select a privileged handle.
            split = self.client.get("/api/portal/itsm", headers=[
                ("Authorization", "Bearer " + VIEWER),
                ("Cookie", COOKIE + "=" + handle),
                ("Cookie", COOKIE + "=" + forged),
            ])
            self._assert_protected(split, 401)
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(handle), None)
            self._assert_protected(self.client.get(
                "/api/portal/itsm", headers={**self._headers(handle), **claims}), 401)
            # Legacy viewer-only status is still constant UNKNOWN, never ALLOW.
            self._assert_protected(self.client.get(
                "/api/portal/itsm", headers=self._headers()), 503)
            core.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()
        receipt("glpi-readmy-human-gate", {
            "explicit_forged_or_revoked_oidc": 401,
            "valid_oidc_without_native_rights": 503,
            "split_cookie_fields": 401,
            "viewer_only": 503,
            "read_vs_readmy_ownership": "UNKNOWN",
            "core_run_variants": len(RUNS),
            "equal_status_projections": True,
            "upstream_business_requests": 0,
            "human_allow": False,
            "independent_glpi_and_core_authorities_attested": False,
            "local_7777_operator_reported": True,
            "external_tls_sso_unique_entrypoint_verified": False,
        })



if __name__ == "__main__":
    unittest.main()
