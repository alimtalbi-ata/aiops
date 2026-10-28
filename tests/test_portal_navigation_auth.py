"""In-process portal navigation RBAC and anonymous HTML disclosure regression.

No external service is contacted. Synthetic test credentials only.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "synthetic-ci-only-internal-token")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi.testclient import TestClient
from portal import main

TOKEN = "synthetic-ci-only-portal-read-credential"
GRAFANA = "https://grafana.example.invalid/d/ops"


class PortalNavigationAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def assert_uncacheable(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")

    def test_unconfigured_denies_before_registry_access(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            main, "build_navigation", side_effect=AssertionError("registry accessed")
        ):
            response = self.client.get("/api/portal/components")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "portal_read_auth_not_configured"})
        self.assert_uncacheable(response)

    def test_missing_or_invalid_bearer_denies_before_registry_access(self):
        for header in (None, "Bearer wrong", "Basic " + TOKEN, "Bearer " + TOKEN + " x"):
            with self.subTest(header=header), patch.dict(
                os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}
            ), patch.object(main, "build_navigation", side_effect=AssertionError("registry accessed")):
                headers = {"Authorization": header} if header is not None else {}
                response = self.client.get("/api/portal/components", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assert_uncacheable(response)

    def test_authorized_registry_is_explicitly_unverified(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_LINK_GRAFANA": GRAFANA}):
            response = self.client.get("/api/portal/components",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assert_uncacheable(response)
        data = response.json()
        self.assertFalse(data["runtime_verified"])
        self.assertFalse(data["live_remediation_authorized"])
        grafana = next(row for row in data["items"] if row["id"] == "grafana")
        self.assertEqual(grafana["external_url"], GRAFANA)
        self.assertEqual(grafana["state"], "UNKNOWN")

    def test_public_html_does_not_expose_configured_urls(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_LINK_GRAFANA": GRAFANA}), patch.object(
            main, "get_json", side_effect=TimeoutError("synthetic upstream down")
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(GRAFANA, response.text)
        self.assertNotIn(TOKEN, response.text)
        self.assertIn("portal-navigation-token", response.text)
        self.assertIn("/assets/portal-navigation.js", response.text)
        self.assertIn("UNKNOWN", response.text)

    def test_invalid_config_is_not_reflected_to_authorized_caller(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_LINK_GLPI": "javascript:alert(1)"}):
            response = self.client.get("/api/portal/components",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("javascript:", response.text)

    def test_script_has_no_persistent_token_or_unsafe_html(self):
        response = self.client.get("/assets/portal-navigation.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("localStorage", response.text)
        self.assertNotIn("sessionStorage", response.text)
        self.assertNotIn("innerHTML", response.text)
        self.assertIn("replaceChildren", response.text)


if __name__ == "__main__":
    unittest.main()
