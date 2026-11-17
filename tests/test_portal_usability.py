"""Portal usability layer endpoint and progressive enhancement contract."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-usability-test-token"}):
    from portal.main import app
from fastapi.testclient import TestClient


class PortalUsabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_home_loads_usability_asset_from_same_origin(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('/assets/portal-usability.js', page.text)
        self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])

    def test_usability_asset_is_local_and_not_cacheable(self):
        response = self.client.get("/assets/portal-usability.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertIn("portal-workspace-nav", response.text)
        self.assertIn("portal-run-filter-input", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_dashboard_keeps_existing_safety_states_and_function_routes(self):
        page = self.client.get("/")
        for expected in (
            "UNKNOWN", "/itsm", "/demo/acme-impact", "/demo/explore-story",
            "portal-navigation.js", "portal-bootstrap.js", "portal-run-link.js",
        ):
            self.assertIn(expected, page.text)


if __name__ == "__main__":
    unittest.main()
