"""Demo Studio is a static presenter aid, not a runtime integration."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "demo-studio-test-only"}):
    from portal import main
from fastapi.testclient import TestClient


class DemoStudioTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def test_demo_studio_is_static_french_presenter_aid(self):
        with patch("portal.demo_studio.PAGE", wraps=__import__(
            "portal.demo_studio", fromlist=["PAGE"]).PAGE):
            response = self.client.get("/demo/studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ACME · Incident majeur SAN", response.text)
        self.assertIn("DEMO STUDIO · SYNTHETIC ONLY", response.text)
        self.assertIn("SIMULATION uniquement", response.text)
        self.assertIn("5 minutes", response.text)
        self.assertIn('href="/demo/acme-impact"', response.text)
        self.assertIn('href="/demo/explore-story"', response.text)
        self.assertIn('href="/itsm"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertNotIn("AIOPS_INTERNAL_TOKEN", response.text)
        self.assertNotIn("SIM-ACME-", response.text)

    def test_studio_does_not_read_fixture_or_call_upstream(self):
        with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
                   side_effect=AssertionError("static page must not read fixture")), \
             patch("portal.main.get_json",
                   side_effect=AssertionError("static page must not call upstream")), \
             patch("portal.main.post_json",
                   side_effect=AssertionError("static page must not call upstream")):
            response = self.client.get("/demo/studio")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
