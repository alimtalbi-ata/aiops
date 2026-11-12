"""Readback comparison tests; no HTTP, GLPI writes, or synthetic ACL grants."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_readback_comparison import compare_raw_readbacks_to_association


class GLPIReadbackComparisonTests(unittest.TestCase):
    def setUp(self):
        self.xref = dict(tenant_id="tenant-a", glpi_instance_id="ci",
                         ticket_id="201", glpi_entity_id="7",
                         incident_id="INC-DEMO-12345678", run_id="RUN-12345678")
        self.core = {"run": {"run_id": "RUN-12345678",
                             "incident_id": "INC-DEMO-12345678", "mode": "DEMO"}}
        self.glpi = {"id": 201, "entities_id": 7, "name": "demo"}

    def test_matching_raw_readbacks_do_not_claim_tenant_or_attestation(self):
        result = compare_raw_readbacks_to_association(
            association=self.xref, core_payload=self.core, glpi_payload=self.glpi)
        self.assertTrue(result["raw_readbacks_match"])
        self.assertFalse(result["canonical_association_attested"])
        self.assertFalse(result["tenant_acl_verified"])
        self.assertFalse(result["actor_acl_verified"])
        self.assertNotIn("glpi_instance_id", result)

    def test_core_incident_mismatch_rejected(self):
        self.core["run"]["incident_id"] = "INC-OTHER-12345678"
        with self.assertRaises(ValueError):
            compare_raw_readbacks_to_association(
                association=self.xref, core_payload=self.core, glpi_payload=self.glpi)

    def test_glpi_entity_mismatch_rejected(self):
        self.glpi["entities_id"] = 9
        with self.assertRaises(ValueError):
            compare_raw_readbacks_to_association(
                association=self.xref, core_payload=self.core, glpi_payload=self.glpi)

    def test_missing_canonical_association_rejected(self):
        with self.assertRaises(ValueError):
            compare_raw_readbacks_to_association(
                association=None, core_payload=self.core, glpi_payload=self.glpi)


if __name__ == "__main__":
    unittest.main()
