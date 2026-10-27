"""Offline unit/route tests; no NOC, Core, GLPI or Debian runtime qualified."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.acme_itsm_correlation import project_correlation, router
from portal.acme_impact_read_model import build_acme_impact_read_model

SCENARIO = build_acme_impact_read_model()
RUN = "RUN-ACME-001"
INCIDENT = "INC-ACME-DEMO-SAN-001"
NOC = {
    "source_payload_authenticated": True,
    "source_payload_sha256": "a" * 64,
    "run_id": RUN,
    "incident_id": INCIDENT,
    "ticket_id": "12345",
}
CORE = {"run": {
    "run_id": RUN, "incident_id": INCIDENT, "mode": "DEMO",
    "version": 2, "scenario_id": "SCN-ACME-SAN-PAYMENTS",
}}

class AcmeCorrelationTests(unittest.TestCase):
    def test_matching_core_and_signed_noc_is_unverified_not_glpi_ticket(self):
        result = project_correlation(SCENARIO, NOC, CORE)
        self.assertEqual(result["state"], "CORRELATED_UNVERIFIED")
        self.assertEqual(result["core_run_id"], RUN)
        self.assertEqual(result["glpi_ticket_claim"], "12345")
        self.assertIsNone(result["ticket_id"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_rejects_live_even_with_matching_ids(self):
        result = project_correlation(SCENARIO, NOC, {"run": {**CORE["run"], "mode": "LIVE"}})
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["core_run_id"])
        self.assertIsNone(result["glpi_ticket_claim"])

    def test_rejects_wrong_incident_or_run(self):
        for noc, core in (
            ({**NOC, "incident_id": "INC-OTHER"}, CORE),
            (NOC, {"run": {**CORE["run"], "run_id": "RUN-OTHER"}}),
            (NOC, {"run": {**CORE["run"], "incident_id": "INC-OTHER"}}),
        ):
            with self.subTest(noc=noc, core=core):
                self.assertEqual(project_correlation(SCENARIO, noc, core)["state"], "UNKNOWN")

    def test_rejects_unverified_signed_payload_and_bad_digest(self):
        for noc in (None, {**NOC, "source_payload_authenticated": False},
                    {**NOC, "source_payload_sha256": "not-a-digest"}):
            with self.subTest(noc=noc):
                self.assertEqual(project_correlation(SCENARIO, noc, CORE)["state"], "UNKNOWN")

    def test_rejects_malformed_or_boolean_core_version(self):
        for version in (True, 0, "1"):
            with self.subTest(version=version):
                core = {"run": {**CORE["run"], "version": version}}
                self.assertEqual(project_correlation(SCENARIO, NOC, core)["state"], "UNKNOWN")

    def test_synthetic_ticket_claim_never_promoted(self):
        result = project_correlation(SCENARIO, {**NOC, "ticket_id": "SIM-GLPI-ABC"}, CORE)
        self.assertIsNone(result["glpi_ticket_claim"])
        self.assertIsNone(result["ticket_id"])

    def test_auth_required_and_missing_config_fails_closed(self):
        app = FastAPI()
        app.include_router(router)
        with patch.dict(os.environ, {}, clear=True):
            response = TestClient(app).get("/api/portal/acme-correlation")
            self.assertEqual(response.status_code, 503)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "test-read-token"}, clear=True):
            response = TestClient(app).get("/api/portal/acme-correlation")
            self.assertEqual(response.status_code, 401)

    def test_missing_noc_source_unknown_not_healthy(self):
        app = FastAPI()
        app.include_router(router)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "test-read-token"}):
            with patch("portal.acme_itsm_correlation.read_signed_noc_snapshot", side_effect=ValueError("offline")):
                response = TestClient(app).get("/api/portal/acme-correlation",
                    headers={"Authorization": "Bearer test-read-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertIsNone(response.json()["ticket_id"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_authenticated_route_correlates_only_matching_core(self):
        app = FastAPI()
        app.include_router(router)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "test-read-token",
                                      "AIOPS_INTERNAL_TOKEN": "unit-test-internal"}):
            with patch("portal.acme_itsm_correlation.read_signed_noc_snapshot", return_value=NOC):
                with patch("shared.http.get_json", return_value=CORE) as get:
                    response = TestClient(app).get("/api/portal/acme-correlation",
                        headers={"Authorization": "Bearer test-read-token"})
                    self.assertEqual(get.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "CORRELATED_UNVERIFIED")
        self.assertIsNone(response.json()["ticket_id"])

    def test_portal_mount(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
            from portal.main import app
        self.assertIn("/api/portal/acme-correlation", {route.path for route in app.routes})

if __name__ == "__main__":
    unittest.main()
