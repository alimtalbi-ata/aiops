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


    def test_decision_cockpit_static_chain(self):
        with patch("portal.main.get_json", side_effect=AssertionError("no upstream")), patch("portal.main.post_json", side_effect=AssertionError("no upstream")), patch("portal.acme_impact_read_model.build_acme_impact_read_model", side_effect=AssertionError("no fixture")):
            response = self.client.get("/demo/decision-cockpit")
        self.assertEqual(response.status_code, 200)
        for stage in ("Analyst", "Critic", "Policy", "HITL", "Simulation", "Verification"):
            self.assertIn("<h2>" + stage + "</h2>", response.text)
        self.assertEqual(response.text.count("Preuve runtime : <strong>MISSING</strong>"), 6)
        self.assertIn("LIVE BLOQUÉ", response.text)
        self.assertIn("NON EFFECTUÉE", response.text)
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn('href="/demo/decision-cockpit"', self.client.get("/demo/studio").text)


    def test_golden_demo_hash_and_no_network(self):
        import hashlib
        import base64
        from portal.demo_studio import GOLDEN_SCRIPT
        response = self.client.get("/demo/golden")
        self.assertEqual(response.status_code, 200)
        digest = base64.b64encode(hashlib.sha256(GOLDEN_SCRIPT.encode()).digest()).decode()
        csp = response.headers["content-security-policy"]
        self.assertIn("script-src 'sha256-" + digest + "'", csp)
        self.assertIn("connect-src 'none'", csp)
        self.assertIn("LIVE BLOQUÉ", response.text)
        self.assertIn("REFUS SIMULÉ", response.text)
        self.assertIn('href="/demo/golden"', self.client.get("/demo/studio").text)
        self.assertNotIn("fetch(", GOLDEN_SCRIPT)
        self.assertNotIn("localStorage", GOLDEN_SCRIPT)
        self.assertEqual(self.client.post("/demo/golden").status_code, 405)


    def test_twin_and_report_are_explicitly_synthetic(self):
        response = self.client.get("/demo/golden")
        self.assertEqual(response.status_code, 200)
        for marker in ("Digital Twin · SYNTHETIC", "fraîcheur runtime UNKNOWN", "AL-SYN-01", "Cible non mesurée", "Rapport d'incident · SYNTHETIC", "NON EFFECTUÉE"):
            self.assertIn(marker, response.text)
        self.assertIn('id="targets" hidden', response.text)
        self.assertIn('id="report" class="card" hidden', response.text)
        from portal.demo_studio import GOLDEN_SCRIPT
        self.assertIn('step<4||decision!=="approved"', GOLDEN_SCRIPT)
        self.assertIn('step!==5&&decision!=="refused"', GOLDEN_SCRIPT)


if __name__ == "__main__":
    unittest.main()
