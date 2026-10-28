"""Offline HTTP contract tests: component navigation metadata requires viewer auth.

These tests do not probe n8n, Thruk, Grafana, GLPI, Debian, or LIVE services.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal import main as portal_main

TOKEN = "synthetic-ci-only-portal-read-credential"


class PortalComponentAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(portal_main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def assert_uncacheable(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")

    def test_missing_configuration_fails_closed_without_reading_registry(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            portal_main, "build_navigation", side_effect=AssertionError("registry accessed")
        ):
            response = self.client.get("/api/portal/components")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "portal_read_auth_not_configured"})
        self.assert_uncacheable(response)

    def test_anonymous_request_cannot_read_configured_navigation(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            portal_main, "build_navigation", side_effect=AssertionError("registry accessed")
        ):
            response = self.client.get("/api/portal/components")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "invalid_portal_read_token"})
        self.assert_uncacheable(response)

    def test_bad_credentials_and_schemes_fail_before_registry_read(self):
        for value in ("Bearer wrong", "Basic " + TOKEN, "Bearer", "Bearer " + TOKEN + "x"):
            with self.subTest(authorization=value), patch.dict(
                os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}
            ), patch.object(
                portal_main, "build_navigation", side_effect=AssertionError("registry accessed")
            ):
                response = self.client.get(
                    "/api/portal/components", headers={"Authorization": value}
                )
                self.assertEqual(response.status_code, 401)
                self.assert_uncacheable(response)

    def test_valid_viewer_token_returns_unattested_navigation(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_LINK_GRAFANA": "https://grafana.example.invalid/d/ops"}):
            response = self.client.get(
                "/api/portal/components", headers={"Authorization": "Bearer " + TOKEN}
            )
        self.assertEqual(response.status_code, 200)
        self.assert_uncacheable(response)
        data = response.json()
        self.assertEqual(data["navigation_mode"], "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY")
        self.assertIs(data["runtime_verified"], False)
        self.assertIs(data["live_remediation_authorized"], False)
        self.assertTrue(all(row["state"] == "UNKNOWN" for row in data["items"]))
        grafana = next(row for row in data["items"] if row["id"] == "grafana")
        self.assertEqual(grafana["external_url"], "https://grafana.example.invalid/d/ops")
        self.assertEqual(grafana["external_link_state"], "CONFIGURED_UNVERIFIED")
        self.assertIs(grafana["runtime_authenticated"], False)

    def test_rejected_configuration_does_not_leak_to_authorized_caller(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_LINK_GLPI": "javascript:alert(1)"}):
            response = self.client.get(
                "/api/portal/components", headers={"Authorization": "Bearer " + TOKEN}
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("javascript:", response.text)
        glpi = next(row for row in response.json()["items"] if row["id"] == "glpi")
        self.assertIsNone(glpi["external_url"])
        self.assertEqual(glpi["external_link_state"], "REJECTED_CONFIGURATION")


if __name__ == "__main__":
    unittest.main()
