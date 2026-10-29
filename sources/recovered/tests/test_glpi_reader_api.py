"""Offline API contract tests. No GLPI container or runtime attestation is implied."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi.testclient import TestClient
from glpi_reader.main import app
from shared.glpi_ticket_read import GLPIUnverified

TOKEN = "g" * 48
HEADERS = {"Authorization": "Bearer " + TOKEN}
ENV = {"AIOPS_GLPI_READER_TOKEN": TOKEN}


class InternalGLPIReaderTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_is_not_attestation(self):
        result = self.client.get("/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["state"], "NOT_ATTESTED")

    def test_unauthorized_never_contacts_glpi(self):
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket", side_effect=AssertionError("network forbidden")
        ) as reader:
            for headers in ({}, {"Authorization": "Bearer bad"},
                            {"Authorization": "Basic " + TOKEN},
                            {"Authorization": "Bearer " + "x" * 48}):
                with self.subTest(headers=headers):
                    response = self.client.get("/internal/glpi/tickets/123", headers=headers)
                    self.assertEqual(response.status_code, 401)
            reader.assert_not_called()

    def test_missing_reader_secret_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_GLPI_READER_TOKEN": ""}), patch(
            "glpi_reader.main.read_ticket", side_effect=AssertionError("network forbidden")
        ) as reader:
            response = self.client.get("/internal/glpi/tickets/123", headers=HEADERS)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "reader_not_configured")
            reader.assert_not_called()

    def test_live_and_unknown_modes_never_contact_glpi(self):
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket", side_effect=AssertionError("network forbidden")
        ) as reader:
            for mode in ("LIVE", "live", "REPLAY", "STORY", ""):
                with self.subTest(mode=mode):
                    response = self.client.get("/internal/glpi/tickets/123",
                                               params={"mode": mode}, headers=HEADERS)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()["state"], "UNKNOWN")
            reader.assert_not_called()

    def test_observation_is_explicitly_uncorrelated(self):
        projected = {
            "schema": "aiops.glpi.ticket-observation.v1",
            "state": "OBSERVED_UNCORRELATED", "ticket_id": "123",
            "run_id": None, "incident_id": None, "correlation_state": "UNKNOWN",
            "runtime_attested": False, "production_qualified": False,
            "live_remediation_authorized": False,
        }
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket", return_value=projected
        ) as reader:
            response = self.client.get("/internal/glpi/tickets/123", headers=HEADERS)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), projected)
            self.assertEqual(response.headers["cache-control"], "no-store")
            reader.assert_called_once_with("123", mode="DEMO")

    def test_glpi_errors_do_not_leak_credentials_or_ticket(self):
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket",
            side_effect=GLPIUnverified("secret " + TOKEN)
        ):
            response = self.client.get("/internal/glpi/tickets/123", headers=HEADERS)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["ticket_id"], None)
            self.assertNotIn(TOKEN, response.text)
            self.assertNotIn("123", response.text)

    def test_invalid_ticket_id_does_not_become_an_observation(self):
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket", side_effect=GLPIUnverified("invalid id")
        ):
            response = self.client.get("/internal/glpi/tickets/SIM-GLPI-123", headers=HEADERS)
            self.assertEqual(response.status_code, 503)
            self.assertIsNone(response.json()["ticket_id"])

    def test_simulation_mode_is_forwarded_without_live_qualification(self):
        with patch.dict(os.environ, ENV), patch(
            "glpi_reader.main.read_ticket",
            return_value={"state": "OBSERVED_UNCORRELATED", "runtime_attested": False}
        ) as reader:
            response = self.client.get("/internal/glpi/tickets/123",
                                       params={"mode": "SIMULATION"}, headers=HEADERS)
            self.assertEqual(response.status_code, 200)
            reader.assert_called_once_with("123", mode="SIMULATION")


if __name__ == "__main__":
    unittest.main()
