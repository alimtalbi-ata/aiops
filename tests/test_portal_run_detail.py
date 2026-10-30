"""Main-based Portal Run detail tests: offline mocks only, no Core/GLPI/DB I/O."""
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-core-test-token"}):
    from portal import main, acme_run_detail
from fastapi.testclient import TestClient

TOKEN = "ci-only-portal-viewer-token"
RID = "RUN-73AFC6FF9315376C"
IID = "INC-GOLDEN-P1-1edd0de6f46546e294139bf68d73d65a"


def run(**changes):
    return {"run_id": RID, "incident_id": IID, "mode": "DEMO",
            "status": "RESOLVED", **changes}


class RunDetailTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN, "AIOPS_PORTAL_COOKIE_SECURE": "false"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def get(self, path=None, authorized=True):
        return self.client.get(path or "/api/portal/runs/" + RID, headers=(
            {"Authorization": "Bearer " + TOKEN} if authorized else {}))

    def test_verified_synthetic_identity_only_never_claims_evidence_or_hitl(self):
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()) as core:
            response = self.get()
        self.assertEqual(response.status_code, 200)
        core.assert_called_once_with(RID)
        data = response.json()
        self.assertEqual(data["connection_state"], "CONNECTED")
        self.assertEqual(data["provenance"], "SYNTHETIC")
        self.assertEqual(data["run_id"], RID)
        self.assertEqual(data["incident_id"], IID)
        self.assertEqual(data["source_freshness"], "UNKNOWN")
        self.assertIsNone(data["source_observed_at"])
        self.assertFalse(data["tenant_acl_qualified"])
        self.assertFalse(data["runtime_attested"])
        self.assertFalse(data["live_remediation_authorized"])
        for key in ("Evidence", "AI Ledger", "Policy", "HITL", "Verification", "GLPI"):
            self.assertEqual(data["journey"][key]["state"], "UNKNOWN")
        self.assertEqual(data["journey"]["GLPI"]["reason"],
                         "NO_TENANT_SCOPED_TICKET_RUN_LINK")
        self.assertEqual(data["journey"]["Evidence"]["reason"],
                         "CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING")
        self.assertNotIn("ticket_id", response.text)
        self.assertNotIn("evidence_id", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")

    def test_auth_missing_and_wrong_never_touch_core(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                response = self.client.get("/api/portal/runs/" + RID, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["state"], "UNAUTHORIZED")
            core.assert_not_called()

    def test_auth_unconfigured_stays_unknown_without_core_read(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
                acme_run_detail, "_read_core_run",
                side_effect=AssertionError("no Core read")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_upstream_401_403_preserved_without_credentials(self):
        for code in (401, 403):
            with self.subTest(code=code), patch.object(
                    acme_run_detail, "_read_core_run",
                    side_effect=urllib.error.HTTPError("http://core", code, "secret", {}, None)):
                response = self.get()
            self.assertEqual(response.status_code, code)
            self.assertEqual(response.json()["state"], "UNAUTHORIZED")
            self.assertNotIn("secret", response.text)

    def test_invalid_identifier_refused_before_core(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")):
            response = self.get("/api/portal/runs/RUN-bad!")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_foreign_run_and_live_are_unknown_not_replaced(self):
        for invalid in (run(run_id="RUN-FOREIGN"), run(mode="LIVE"),
                        run(incident_id="INC-FOREIGN"), run(status="")):
            with self.subTest(invalid=invalid), patch.object(
                    acme_run_detail, "_read_core_run", return_value=invalid):
                response = self.get()
            # An independently valid foreign incident ID is NOT an asserted match.
            if invalid.get("incident_id") == "INC-FOREIGN":
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["incident_id"], "INC-FOREIGN")
            else:
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_unqualified_collections_and_tenant_claims_rejected(self):
        for change in ({"events": [{"run_id": "RUN-FOREIGN"}]},
                       {"gates": "malformed"},
                       {"stages": []},
                       {"evidence_refs": [{"run_id": "RUN-FOREIGN"}]},
                       {"demo_artifacts": []},
                       {"metadata": {"ownerTenantId": "PRIVATE-TENANT"}}):
            with self.subTest(change=change), patch.object(
                    acme_run_detail, "_read_core_run", return_value=run(**change)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            self.assertNotIn("PRIVATE-TENANT", response.text)
            self.assertNotIn("RUN-FOREIGN", response.text)

    def test_core_exception_is_redacted_unknown(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=ValueError("secret-in-upstream")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("secret-in-upstream", response.text)

    def test_core_timeout_is_unavailable(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=TimeoutError("sensitive host")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNAVAILABLE")
        self.assertNotIn("sensitive host", response.text)

    def test_html_page_is_same_portal_route_and_fail_closed_without_auth(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no anonymous read")):
            response = self.get("/runs/" + RID, authorized=False)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Requested Run — NOT VERIFIED", response.text)
        self.assertIn("UNKNOWN", response.text)
        self.assertIn('href="/"', response.text)
        self.assertIn('href="#evidence"', response.text)
        self.assertIn('href="#ai-ledger"', response.text)
        self.assertIn('href="#verification"', response.text)
        self.assertIn('href="#glpi"', response.text)
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_authenticated_html_is_escaped_and_still_unknown_for_evidence(self):
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()):
            response = self.get("/runs/" + RID)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Core-verified Run", response.text)
        self.assertIn("SYNTHETIC", response.text)
        self.assertIn("CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING", response.text)
        self.assertIn("TENANT_ACL_NOT_QUALIFIED", response.text)
        self.assertIn("source freshness: UNKNOWN", response.text)
        self.assertNotIn("<script", response.text)

    def test_home_entry_and_js_asset_do_not_ship_secrets(self):
        home = self.client.get("/")
        self.assertIn('id="run-detail-id"', home.text)
        self.assertIn('id="run-detail-open"', home.text)
        self.assertIn('/assets/portal-run-link.js', home.text)
        js = self.client.get("/assets/portal-run-link.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])
        for forbidden in ("localStorage", "sessionStorage", "document.cookie", "token="):
            self.assertNotIn(forbidden, js.text)
        self.assertIn("Authorization: 'Bearer ' + token", js.text)
        self.assertIn("credentials: 'same-origin'", js.text)
        self.assertIn("portal-read-token", js.text)

    def test_same_origin_session_exchange_sets_short_lived_httponly_cookie_and_opens_page(self):
        response = self.client.post(
            "/api/portal/run-session",
            headers={"Authorization": "Bearer " + TOKEN, "Origin": "http://testserver",
                     "X-Portal-Run-ID": RID},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "READ_ONLY_SESSION_CREATED")
        cookie = response.headers["set-cookie"]
        self.assertIn("httponly", cookie.lower())
        self.assertIn("samesite=strict", cookie.lower())
        self.assertIn("path=/runs", cookie.lower())
        self.assertIn("max-age=300", cookie.lower())
        self.assertNotIn(TOKEN, cookie)
        self.assertNotIn("; secure", cookie.lower())
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()) as core:
            page = self.client.get("/runs/" + RID)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Core-verified Run", page.text)
        core.assert_called_once_with(RID)

    def test_session_exchange_rejects_missing_token_and_cross_origin(self):
        missing = self.client.post("/api/portal/run-session")
        self.assertEqual(missing.status_code, 401)
        self.assertNotIn("set-cookie", missing.headers)
        cross = self.client.post(
            "/api/portal/run-session",
            headers={"Authorization": "Bearer " + TOKEN, "Origin": "https://evil.example"},
        )
        self.assertEqual(cross.status_code, 403)
        self.assertNotIn("set-cookie", cross.headers)

    def test_expired_or_tampered_session_never_reads_core(self):
        with patch.object(acme_run_detail.time, "time", return_value=1000):
            expired = acme_run_detail._issue_session(RID, now=1000)
        self.client.cookies.set(acme_run_detail.SESSION_COOKIE, expired, path="/runs")
        with patch.object(acme_run_detail.time, "time", return_value=1400), patch.object(
            acme_run_detail, "_read_core_run", side_effect=AssertionError("no Core read")
        ) as core:
            response = self.client.get("/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()
        self.client.cookies.set(acme_run_detail.SESSION_COOKIE, "tampered.payload", path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            response = self.client.get("/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()

    def test_json_run_api_remains_bearer_only_even_with_html_session_cookie(self):
        self.client.cookies.set(
            acme_run_detail.SESSION_COOKIE, acme_run_detail._issue_session(RID), path="/runs"
        )
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            response = self.client.get("/api/portal/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()

    def test_session_cookie_can_be_secure_when_portal_is_behind_tls(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_COOKIE_SECURE": "true"}):
            response = self.client.post(
                "/api/portal/run-session",
                headers={"Authorization": "Bearer " + TOKEN, "X-Portal-Run-ID": RID},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("; secure", response.headers["set-cookie"].lower())

    def test_session_exchange_requires_valid_run_scope_before_cookie(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            for rid in (None, "RUN-../foreign", "INC-123"):
                headers = {"Authorization": "Bearer " + TOKEN}
                if rid is not None:
                    headers["X-Portal-Run-ID"] = rid
                response = self.client.post("/api/portal/run-session", headers=headers)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["state"], "UNKNOWN")
                self.assertNotIn("set-cookie", response.headers)
            core.assert_not_called()

    def test_cookie_cannot_open_another_run_even_with_valid_signature(self):
        cookie = acme_run_detail._issue_session(RID)
        self.client.cookies.set(acme_run_detail.SESSION_COOKIE, cookie, path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("foreign Core read")) as core:
            foreign = self.client.get("/runs/RUN-OTHER-123")
        self.assertEqual(foreign.status_code, 401)
        self.assertIn("NOT VERIFIED", foreign.text)
        core.assert_not_called()
        self.assertTrue(acme_run_detail._valid_session(cookie, RID))
        self.assertFalse(acme_run_detail._valid_session(cookie, "RUN-OTHER-123"))

    def test_rotated_read_token_revokes_existing_run_session(self):
        cookie = acme_run_detail._issue_session(RID)
        self.client.cookies.set(acme_run_detail.SESSION_COOKIE, cookie, path="/runs")
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "rotated-ci-only-viewer-token"}):
            self.assertFalse(acme_run_detail._valid_session(cookie, RID))
            with patch.object(acme_run_detail, "_read_core_run",
                              side_effect=AssertionError("no Core read")) as core:
                response = self.client.get("/runs/" + RID)
            self.assertEqual(response.status_code, 401)
            core.assert_not_called()

    def test_existing_home_cockpit_is_no_store_and_anti_framing(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        policy = response.headers["content-security-policy"]
        for directive in ("default-src 'none'", "connect-src 'self'",
                          "frame-ancestors 'none'", "base-uri 'none'",
                          "object-src 'none'"):
            self.assertIn(directive, policy)
        # Legacy inline event handlers stay functional; no parallel shell.
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn('id="run-detail-open"', response.text)
        self.assertIn('id="portal-runs"', response.text)

    def test_unverified_run_html_stays_no_store_with_security_headers(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=ValueError("unqualified Core payload")):
            response = self.get("/runs/" + RID)
        self.assertEqual(response.status_code, 503)
        self.assertIn("UNKNOWN", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        self.assertNotIn("unqualified Core payload", response.text)

    def test_no_new_write_endpoint(self):
        self.assertEqual(self.client.post("/api/portal/runs/" + RID).status_code, 405)
        self.assertEqual(self.client.post("/runs/" + RID).status_code, 405)


if __name__ == "__main__":
    unittest.main()
