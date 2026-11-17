"""Shared Portal theme coverage: all HTML surfaces use the local design system."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-theme-test-token"}):
    from portal.main import app
from fastapi.testclient import TestClient


class PortalThemeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_theme_stylesheet_is_local_and_served(self):
        response = self.client.get("/assets/aiops-theme.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.headers["content-type"])
        self.assertIn("--ai-violet: #8b5cf6", response.text)
        self.assertIn("--ai-blue: #38bdf8", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_all_portal_html_surfaces_load_shared_theme(self):
        for path in ("/", "/itsm", "/demo/explore-story", "/demo/acme-impact"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('/assets/aiops-theme.css', response.text)
                self.assertIn("'self'", response.headers["content-security-policy"])
                self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_api_responses_are_not_rewritten_as_html(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('/assets/aiops-theme.css', response.text)


if __name__ == "__main__":
    unittest.main()
