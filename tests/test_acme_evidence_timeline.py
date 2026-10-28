"""ACME timeline contract: deterministic synthetic view, negative and HTTP tests only."""
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_evidence_timeline import build_acme_evidence_timeline, router


class AcmeEvidenceTimelineTests(unittest.TestCase):
    def setUp(self):
        self.source = build_acme_impact_read_model()

    def test_nine_missing_checkpoints_and_no_fabricated_business_measure(self):
        result = build_acme_evidence_timeline(self.source)
        self.assertEqual(result, build_acme_evidence_timeline(self.source))
        self.assertEqual(len(result["timeline"]), 9)
        self.assertEqual([e["sequence"] for e in result["timeline"]], list(range(1, 10)))
        self.assertTrue(all(e["evidence_status"] == "MISSING" and
                            e["observed_at_utc"] is None and
                            e["capture_sha256"] is None and
                            not e["runtime_authenticated"] for e in result["timeline"]))
        self.assertEqual(result["run_id"], self.source["run_id"])
        self.assertIsNone(result["glpi_ticket_id"])
        self.assertFalse(result["video_ready"])
        self.assertFalse(result["production_qualified"])
        business = result["business_summary"]
        self.assertEqual(business["dependency_path"], self.source["impact_path"])
        self.assertEqual(business["potentially_affected_ci_count_from_fixture"],
                         len(self.source["affected_ci_ids"]))
        self.assertIsNone(business["observed_financial_loss_eur"])
        self.assertIsNone(business["observed_downtime_minutes"])
        self.assertEqual(business["observed_service_availability"], "UNKNOWN")

    def test_rejects_claimed_live_and_runtime_proof(self):
        for field, value in (("provenance", "LIVE"), ("runtime_attested", True),
                             ("runtime_evidence_present", True),
                             ("production_qualified", True),
                             ("live_remediation_authorized", True),
                             ("ticket_id", "1234"),
                             ("event_timestamp_utc", "2026-10-28T10:00:00Z"),
                             ("run_id", "RUN-REAL"),
                             ("simulation_ticket_id", "SIM-GLPI-FORGED")):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.source)
                bad[field] = value
                with self.assertRaises(ValueError):
                    build_acme_evidence_timeline(bad)

    def test_rejects_injected_capture_and_wrong_checkpoint(self):
        for field, value in (("status", "VERIFIED"),
                             ("screenshot_sha256", "a" * 64),
                             ("event_timestamp_utc", "2026-10-28T10:00:00Z"),
                             ("runtime_authenticated", True),
                             ("source", "LIVE_CAPTURE"),
                             ("cue", "close"),
                             ("service", "glpi")):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.source)
                bad["checkpoint_evidence"][0][field] = value
                with self.assertRaises(ValueError):
                    build_acme_evidence_timeline(bad)

    def test_rejects_missing_or_tampered_graph(self):
        for field, value in (("source_sha256", "0" * 64),
                             ("impact_path", ["SAN-FABRIC-A", "APP-PAY-01"]),
                             ("affected_ci_ids", ["APP-PAY-01"]),
                             ("checkpoint_evidence", [])):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.source)
                bad[field] = value
                with self.assertRaises(ValueError):
                    build_acme_evidence_timeline(bad)

    def test_api_html_security_and_no_video_claim(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        response = client.get("/api/demo/acme-evidence-timeline")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["capture_status"], "BLOCKED_NO_AUTHENTICATED_CAPTURES")
        page = client.get("/demo/acme-evidence-timeline")
        self.assertEqual(page.status_code, 200)
        self.assertIn("SIMULATION LOCALE UNIQUEMENT", page.text)
        self.assertIn("Vidéo client BLOQUÉE", page.text)
        self.assertIn("MISSING", page.text)
        self.assertNotIn("<script", page.text)
        self.assertNotIn("10.79.94.202", page.text)

    def test_bad_source_returns_503_not_a_successful_story(self):
        app = FastAPI()
        app.include_router(router)
        with patch("portal.acme_evidence_timeline.build_acme_impact_read_model",
                   side_effect=ValueError("bad fixture")):
            response = TestClient(app).get("/api/demo/acme-evidence-timeline")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("SIM-ACME-", response.text)

    def test_canonical_portal_mount(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
            from portal.main import app
        paths = {route.path for route in app.routes}
        self.assertIn("/api/demo/acme-evidence-timeline", paths)
        self.assertIn("/demo/acme-evidence-timeline", paths)


if __name__ == "__main__":
    unittest.main()
