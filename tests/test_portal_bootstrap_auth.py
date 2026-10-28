"""HTTP regression for anonymous shell and PR #36-inspired read-token bootstrap.

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

    def test_valid_read_token_only_reads_expected_sources_and_is_unattested(self):
        calls = []
        def fake_read(base, path):
            calls.append((base, path))
            return VALID[path]
        with patch.object(main, "get_json", side_effect=fake_read), patch.object(
            main, "post_json", side_effect=AssertionError("no writes")
        ):
            response = self.client.get("/api/portal/bootstrap",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["states"],
                         {"dashboard": "READABLE_UNVERIFIED", "runs": "READABLE_UNVERIFIED",
                          "twin": "READABLE_UNVERIFIED"})
        self.assertFalse(response.json()["runtime_authenticated"])
        self.assertFalse(response.json()["live_remediation_authorized"])
        self.assertEqual(calls, [(main.CORE, "/api/dashboard"),
                                 (main.CORE, "/api/runs"),
                                 (main.TWIN, "/api/twin/summary")])

    def test_failed_upstream_remains_unknown_not_success(self):
        with patch.object(main, "get_json", side_effect=TimeoutError("secret-internal-host")):
            response = self.client.get("/api/portal/bootstrap",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["states"].values()), {"UNKNOWN"})
        self.assertIsNone(response.json()["runs"])
        self.assertNotIn("secret-internal-host", response.text)

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
