"""#386: historical Demo Studio renderer, mounted without Run/tenant data leakage."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "disposable-ci-only-no-live")
from portal.main import app


class HistoricalDemoStudio386Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_historical_renderer_is_reachable_from_demonstration_center(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/demo-studio", paths)
        self.assertIn('href="/demo-studio"', self.client.get("/demo-center").text)
        response = self.client.get("/demo-studio")
        self.assertEqual(response.status_code, 200)
        for marker in ("Mission Control V2", "Chronologie canonique",
                       "Policy", "DemoCenter", "SYNTHETIC_REFERENCE_ONLY",
                       "NO LIVE EFFECT", "INCONNU", "UNKNOWN",
                       "Analyst/Critic", "/runs/{rid}"):
            self.assertIn(marker, response.text)
        self.assertNotIn("EVD-1", response.text)
        self.assertNotIn("RUN-1", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("form-action 'none'", response.headers["content-security-policy"])
        self.assertEqual(self.client.post("/demo-studio").status_code, 405)

    def test_anonymous_studio_does_not_fetch_core_twin_glpi_or_create_run(self):
        with patch("shared.http.get_json", side_effect=AssertionError("upstream read")), \
             patch("shared.http.post_json", side_effect=AssertionError("upstream write")):
            response = self.client.get("/demo-studio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Aucun Run", response.text)
        self.assertNotIn("TWIN_ACME_SIMULATED</", response.text)

    def test_historical_renderer_escapes_untrusted_evidence_and_run_fields(self):
        from portal.demo_v2 import render_demo_v2
        payload = '<img src=x onerror=alert(1)>'
        page = render_demo_v2(
            {"run": {"run_id": payload, "mode": "DEMO", "status": "RESOLVED"},
             "events": [{"stage": payload, "evidence_ids": [payload]}]},
            {"status": "UNKNOWN"},
            {"items": [{"stage": payload, "decision": payload}]},
        )
        self.assertNotIn(payload, page)
        self.assertIn("&lt;img", page)
        self.assertIn("RESOLVED", page)
        self.assertIn("Les identifiants sont des références Core", page)


if __name__ == "__main__":
    unittest.main()
