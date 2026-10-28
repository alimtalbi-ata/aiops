"""Offline ACME Core Run readback contract tests; no real Core/GLPI calls."""
import copy
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from portal import acme_run_readback as readback  # noqa: E402
from portal.acme_impact_read_model import build_acme_impact_read_model  # noqa: E402

TOKEN = "acme-operator-read-test-token-32-characters"
RUN_ID = "RUN-ACME-READBACK-001"


def canonical_run():
    return {
        "run_id": RUN_ID,
        "incident_id": "INC-ACME-DEMO-SAN-001",
        "scenario_id": "SCN-GOLDEN-PAYMENT-P1",
        "mode": "DEMO",
        "status": "RUNNING",
        "version": 2,
        "private_payload": "must-never-leak",
        "glpi_ticket_id": "unverified-123",
    }


class AcmeReadbackTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(readback.router)
        self.client = TestClient(app)
        self.fixture = build_acme_impact_read_model()

    def request(self, token=TOKEN, run_id=RUN_ID):
        headers = {"Authorization": "Bearer " + token} if token else {}
        return self.client.get("/api/demo/acme-run/" + run_id, headers=headers)

    def test_exact_demo_run_is_matched_but_unattested(self):
        a = readback.project_acme_run(RUN_ID, canonical_run(), self.fixture)
        b = readback.project_acme_run(RUN_ID, canonical_run(), self.fixture)
        self.assertEqual(a, b)
        self.assertEqual(a["state"], "MATCHED_UNATTESTED")
        self.assertEqual(a["canonical_incident_id"], "INC-ACME-DEMO-SAN-001")
        self.assertEqual(a["fixture_impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(a["fixture_sha256"], self.fixture["source_sha256"])
        self.assertEqual(a["run_status"], "RUNNING")
        self.assertIsNone(a["glpi_ticket_id"])
        self.assertEqual(a["glpi_correlation"], "UNKNOWN")
        self.assertEqual(a["execution_evidence"], "NOT_TESTED")
        self.assertFalse(a["runtime_attested"])
        self.assertFalse(a["live_remediation_authorized"])
        self.assertNotIn("must-never-leak", str(a))
        self.assertNotIn("unverified-123", str(a))

    def test_live_replay_story_and_mismatched_identity_are_unknown(self):
        for change in (
            {"mode": "LIVE"}, {"mode": "REPLAY"}, {"mode": "STORY"},
            {"run_id": "RUN-OTHER"}, {"incident_id": "INC-OTHER-TENANT"},
            {"scenario_id": "SCN-OTHER"}, {"version": 0},
            {"version": True}, {"version": "2"}, {"status": "UNKNOWN"},
            {"status": ["RUNNING"]},
        ):
            with self.subTest(change=change):
                result = readback.project_acme_run(
                    RUN_ID, {**canonical_run(), **change}, self.fixture
                )
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["canonical_run_id"])
                self.assertIsNone(result["canonical_incident_id"])
                self.assertIsNone(result["glpi_ticket_id"])
                self.assertFalse(result["runtime_attested"])
                self.assertNotIn("OTHER-TENANT", str(result))

    def test_invalid_fixture_fails_closed(self):
        for change in (
            {"provenance": "LIVE"}, {"ticket_id": "42"},
            {"runtime_attested": True}, {"live_remediation_authorized": True},
            {"incident_id": "OTHER"}, {"impact_incident_id": "OTHER"},
            {"source_sha256": "g" * 64}, {"source_sha256": "a" * 63},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                readback.project_acme_run(
                    RUN_ID, canonical_run(), {**self.fixture, **change}
                )

    def test_invalid_run_id_rejected_before_any_core_network(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            readback.noc_correlation, "_read_core_run",
            side_effect=AssertionError("no Core request")
        ):
            for bad in ("RUN-INVALID%2Fetc", "RUN-INVALID..%2F", "RUN-X%3Fq"):
                with self.subTest(bad=bad):
                    response = self.request(run_id=bad)
                    self.assertNotEqual(response.status_code, 200)

    def test_auth_denial_blocks_fixture_and_core_reads(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            readback, "build_acme_impact_read_model",
            side_effect=AssertionError("no fixture read")
        ), patch.object(
            readback.noc_correlation, "_read_core_run",
            side_effect=AssertionError("no Core request")
        ):
            for token in (None, "bad"):
                with self.subTest(token=token):
                    response = self.request(token=token)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["cache-control"], "no-store")

    def test_missing_operator_configuration_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            readback.noc_correlation, "_read_core_run",
            side_effect=AssertionError("no Core request")
        ):
            response = self.request()
        self.assertEqual(response.status_code, 503)

    def test_route_returns_only_allowlisted_data(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            readback.noc_correlation, "_read_core_run", return_value=canonical_run()
        ):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "MATCHED_UNATTESTED")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("private_payload", response.text)
        self.assertNotIn("unverified-123", response.text)

    def test_live_run_response_never_leaks_canonical_identity(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            readback.noc_correlation, "_read_core_run",
            return_value={**canonical_run(), "mode": "LIVE",
                          "incident_id": "INC-OTHER-TENANT"}
        ):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertIsNone(response.json()["canonical_run_id"])
        self.assertNotIn("OTHER-TENANT", response.text)

    def test_core_failure_is_redacted(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
            readback.noc_correlation, "_read_core_run",
            side_effect=RuntimeError("PRIVATE-CORE-CREDENTIAL")
        ):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE-CORE-CREDENTIAL", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_portal_displays_separate_readback_control(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "test-internal-only"}):
            from portal.main import app
        with patch("portal.main.read_portal_snapshot", return_value={
            "dashboard": None, "runs": None, "twin": None,
            "states": {"core": "UNKNOWN"}
        }), patch("portal.main.build_navigation", return_value=[]), patch(
            "portal.main.render_navigation_html", return_value=""
        ):
            response = TestClient(app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="acme-run-id"', response.text)
        self.assertIn('id="acme-read-token"', response.text)
        self.assertIn("readAcmeRun()", response.text)
        self.assertIn("UNKNOWN — aucune lecture Core", response.text)
        self.assertNotIn("localStorage", response.text)

    def test_canonical_portal_mounts_readback_route(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "test-internal-only"}):
            from portal.main import app
        self.assertIn("/api/demo/acme-run/{run_id}", {r.path for r in app.routes})


if __name__ == "__main__":
    unittest.main()
