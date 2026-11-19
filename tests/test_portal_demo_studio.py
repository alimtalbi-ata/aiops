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

    def test_static_five_minute_french_presenter_page(self):
        response = self.client.get("/demo/studio")
        self.assertEqual(response.status_code, 200)
        for marker in ("ACME · Incident majeur SAN", "DEMO STUDIO · SYNTHETIC ONLY",
                       "SIMULATION uniquement", "5 minutes",
                       'href="/demo/acme-impact"', 'href="/demo/explore-story"',
                       'href="/itsm"'):
            self.assertIn(marker, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertNotIn("SIM-ACME-", response.text)

    def test_static_route_does_not_read_fixture_or_call_upstream(self):
        with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
                   side_effect=AssertionError("must not read fixture")), \
             patch("portal.main.get_json",
                   side_effect=AssertionError("must not call upstream")), \
             patch("portal.main.post_json",
                   side_effect=AssertionError("must not call upstream")):
            response = self.client.get("/demo/studio")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
