"""HTTP regression for anonymous shell and shared PR #36 NOC read-token bootstrap.

Uses TestClient with patched in-process HTTP adapter: NOT an integration test.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-test-only-internal-token"}):
    from portal import main

from fastapi.testclient import TestClient

TOKEN = "synthetic-portal-read-token"
VALID = {
    "/api/dashboard": {"open_p1": 1, "open_incidents": 2, "running": 0,
                       "blocked": 0, "twin_nodes": 3, "degraded_nodes": 0},
    "/api/runs": {"items": [{"run_id": "DEMO-RUN-1", "mode": "DEMO", "status": "BLOCKED"}]},
    "/api/twin/summary": {"nodes": 3, "edges": 2},
}


class PortalBootstrapAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def test_missing_token_and_wrong_scheme_never_read_core_or_twin(self):
        for headers in ({}, {"Authorization": "Basic " + TOKEN},
                        {"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + TOKEN + " trailing"},
                        {"Authorization": "Bearer"}):
            with self.subTest(headers=headers), patch.object(
                main, "get_json", side_effect=AssertionError("no upstream on denial")
            ) as get:
                response = self.client.get("/api/portal/bootstrap", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "invalid_portal_read_token"})
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                get.assert_not_called()

    def test_unconfigured_auth_fails_closed_without_backend_reads(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            main, "get_json", side_effect=AssertionError("no upstream on denial")
        ) as get:
            response = self.client.get("/api/portal/bootstrap",
                                       headers={"Authorization": "Bearer " + TOKEN})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "portal_read_auth_not_configured")
            get.assert_not_called()

    def test_valid_shared_token_cannot_read_unscoped_tenant_data(self):
        with patch.object(main, "get_json",
                          side_effect=AssertionError("unscoped Core/Twin read")) as get, patch.object(
            main, "post_json", side_effect=AssertionError("no writes")
        ) as post:
            response = self.client.get("/api/portal/bootstrap",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(response.json()["connection_state"], "UNKNOWN")
        self.assertEqual(response.json()["source_freshness"], "UNKNOWN")
        for field in ("dashboard", "runs", "twin", "run_id", "incident_id"):
            self.assertNotIn(field, response.json())
        self.assertEqual(response.headers["cache-control"], "no-store")
        get.assert_not_called()
        post.assert_not_called()

    def test_bootstrap_denies_before_even_attempting_upstream_read(self):
        with patch.object(main, "get_json",
                          side_effect=TimeoutError("secret-internal-host")) as get:
            response = self.client.get("/api/portal/bootstrap",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertNotIn("secret-internal-host", response.text)
        get.assert_not_called()

    def test_anonymous_home_is_shell_without_backend_reads_or_token(self):
        with patch.object(main, "get_json", side_effect=AssertionError("no anonymous Core read")) as get:
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("portal-read-token", response.text)
        self.assertIn("UNKNOWN", response.text)
        self.assertIn('/assets/portal-bootstrap.js', response.text)
        self.assertNotIn(TOKEN, response.text)
        get.assert_not_called()

    def test_browser_script_served_as_js_without_secrets(self):
        response = self.client.get("/assets/portal-bootstrap.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("textContent", response.text)
        self.assertNotIn("localStorage", response.text)
        self.assertNotIn("innerHTML", response.text)


if __name__ == "__main__":
    unittest.main()
