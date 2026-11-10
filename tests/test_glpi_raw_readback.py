"""Offline contract tests for legacy Core/GLPI raw readback shapes."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_raw_readback import (
    RawReadbackInvalid, normalize_core_run_readback, normalize_glpi_ticket_readback
)


class RawReadbackTests(unittest.TestCase):
    def test_core_nested_run_requires_matching_id_and_incident(self):
        payload = {"run": {"run_id": "RUN-12345678",
                           "incident_id": "INC-DEMO-12345678", "mode": "DEMO"}}
        result = normalize_core_run_readback(payload, expected_run_id="RUN-12345678")
        self.assertEqual(result["incident_id"], "INC-DEMO-12345678")
        self.assertNotIn("tenant_id", result)
        self.assertNotIn("core_run_readback_verified", result)
        for wrong in ({"run": {}}, {"run": dict(payload["run"], mode="PROD")},
                      {"run": dict(payload["run"], incident_id="")}):
            with self.assertRaises(RawReadbackInvalid):
                normalize_core_run_readback(wrong, expected_run_id="RUN-12345678")

    def test_glpi_numeric_id_and_entity_are_normalized_without_attestation(self):
        result = normalize_glpi_ticket_readback(
            {"id": 201, "entities_id": 7, "name": "RUN-12345678"},
            expected_ticket_id="201")
        self.assertEqual(result, {"ticket_id": "201", "glpi_entity_id": "7"})
        self.assertNotIn("run_id", result)
        self.assertNotIn("glpi_ticket_readback_verified", result)

    def test_glpi_entity_canonical_numeric_format(self):
        for entity in ("007", "00", "01", "0" * 19):
            with self.subTest(entity=entity), self.assertRaises(RawReadbackInvalid):
                normalize_glpi_ticket_readback(
                    {"id": 201, "entities_id": entity}, expected_ticket_id="201")
        self.assertEqual(normalize_glpi_ticket_readback(
            {"id": 201, "entities_id": 0}, expected_ticket_id="201")
            ["glpi_entity_id"], "0")

    def test_glpi_missing_entity_or_mismatched_ticket_fails(self):
        for ticket in ({"id": 201}, {"id": 202, "entities_id": 7},
                       {"id": True, "entities_id": 7},
                       {"id": 201, "entities_id": True}):
            with self.subTest(ticket=ticket), self.assertRaises(RawReadbackInvalid):
                normalize_glpi_ticket_readback(ticket, expected_ticket_id="201")


if __name__ == "__main__":
    unittest.main()
