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
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
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
        self.assertFalse(data["tenant_acl_qualified"])
        self.assertFalse(data["runtime_attested"])
        self.assertFalse(data["live_remediation_authorized"])
        for key in ("Evidence", "AI Ledger", "Policy", "HITL", "Verification"):
            self.assertEqual(data["journey"][key]["state"], "UNKNOWN")
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
        self.assertNotIn("<script", response.text)

    def test_home_entry_and_js_asset_do_not_ship_secrets(self):
        home = self.client.get("/")
        self.assertIn('id="run-detail-id"', home.text)
        self.assertIn('id="run-detail-open"', home.text)
        self.assertIn('/assets/portal-run-link.js', home.text)
        js = self.client.get("/assets/portal-run-link.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])
        for forbidden in ("localStorage", "sessionStorage", "Authorization", "Bearer", "fetch("):
            self.assertNotIn(forbidden, js.text)

    def test_no_new_write_endpoint(self):
        self.assertEqual(self.client.post("/api/portal/runs/" + RID).status_code, 405)
        self.assertEqual(self.client.post("/runs/" + RID).status_code, 405)


if __name__ == "__main__":
    unittest.main()
