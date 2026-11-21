"""V3 read-only cockpit adapter: contract, routes and fail-closed negative tests."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from portal.main import app
from portal.acme_v3_cockpit_adapter import build_v3_synthetic_cockpit

class V3CockpitAdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_projection_has_no_runtime_authority(self):
        value = build_v3_synthetic_cockpit()
        self.assertEqual(value["overall_qualification"], "UNKNOWN")
        self.assertFalse(value["runtime_attested"])
        self.assertFalse(value["live_remediation_authorized"])
        journey = value["run_journey"]
        self.assertEqual(journey["scope"], "STORY_OFFLINE")
        self.assertIsNone(journey["receipt"])
        self.assertIsNone(journey["run"]["executed_sha"])
        self.assertEqual(journey["policy"]["decision"], "DENY_LIVE_ACTION")
        self.assertEqual(len(journey["stage_plan"]), 17)
        self.assertTrue(all(x["status"] == "NOT_RUN" and x["evidence_state"] == "MISSING"
                            for x in journey["stage_plan"]))

    def test_json_and_html_routes_are_read_only(self):
        response = self.client.get("/api/demo/v3/acme-incident-cockpit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_journey"]["scope"], "STORY_OFFLINE")
        self.assertEqual(response.headers["cache-control"], "no-store")
        page = self.client.get("/demo/v3/acme-incident-cockpit")
        self.assertEqual(page.status_code, 200)
        self.assertIn("NO-GO LIVE", page.text)
        self.assertEqual(page.headers["x-content-type-options"], "nosniff")

    def test_legacy_impact_endpoint_is_unchanged(self):
        response = self.client.get("/api/demo/acme-impact")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("twin_evidence", response.json())
        self.assertFalse(response.json()["live_remediation_authorized"])

    def test_fixture_digest_drift_fails_closed(self):
        from portal import acme_v3_cockpit_adapter as adapter
        real = adapter.build_acme_impact_read_model
        def altered():
            value = real()
            value["source_sha256"] = "0" * 64
            return value
        with patch.object(adapter, "build_acme_impact_read_model", side_effect=altered):
            response = self.client.get("/api/demo/v3/acme-incident-cockpit")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("source_sha256", response.text)

    def test_missing_fixture_fails_closed(self):
        from portal import acme_v3_cockpit_adapter as adapter
        with patch.object(adapter, "_read_fixture_bytes_safely", side_effect=OSError("missing")):
            response = self.client.get("/api/demo/v3/acme-incident-cockpit")
        self.assertEqual(response.status_code, 503)

if __name__ == "__main__":
    unittest.main()
