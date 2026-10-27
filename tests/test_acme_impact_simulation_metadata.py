"""Regression tests for honest, deterministic ACME simulation metadata."""
from __future__ import annotations

import hashlib
import pathlib
import sys
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from portal.acme_impact_read_model import (  # noqa: E402
    build_acme_impact_read_model,
    router,
)


class AcmeImpactSimulationMetadataTests(unittest.TestCase):
    def test_simulation_identifiers_are_deterministic_and_not_real_records(self):
        first = build_acme_impact_read_model()
        second = build_acme_impact_read_model()

        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(first["simulation_ticket_id"], second["simulation_ticket_id"])
        self.assertEqual(
            first["simulation_ticket_id"],
            "SIM-GLPI-" + first["source_sha256"][:12].upper(),
        )
        self.assertEqual(
            first["simulation_checkpoint_timestamp_utc"], "2026-10-25T09:00:00Z"
        )
        self.assertEqual(
            first["simulation_ticket_provenance"],
            "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET",
        )
        self.assertEqual(
            first["simulation_timestamp_provenance"],
            "FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT",
        )
        self.assertIsNone(first["ticket_id"])
        self.assertIsNone(first["event_timestamp_utc"])
        self.assertIs(first["runtime_attested"], False)
        self.assertIs(first["production_qualified"], False)
        self.assertIs(first["live_remediation_authorized"], False)

    def test_portal_html_distinguishes_simulated_metadata_from_runtime_gaps(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.get("/demo/acme-impact")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ticket GLPI réel", response.text)
        self.assertIn("Horodatage runtime réel", response.text)
        self.assertIn("Ticket de scénario (fictif)", response.text)
        self.assertIn("Horodatage de checkpoint (fictif)", response.text)
        self.assertIn("SYNTHETIC_LABEL_NOT_A_GLPI_TICKET", response.text)
        self.assertIn("FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT", response.text)
        self.assertIn("aucun ticket GLPI ni événement runtime n'existe", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("connect-src 'none'", response.headers["content-security-policy"])


if __name__ == "__main__":
    unittest.main()
