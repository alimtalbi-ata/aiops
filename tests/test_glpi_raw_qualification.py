"""Offline orchestration tests for signed xref + raw Core/GLPI reads."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_raw_qualification import (
    GLPIRawQualificationBlocked, qualify_raw_glpi_core_readbacks,
)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.claims = dict(actor="operator", tenant_id="tenant-a",
                           ticket_id="201", glpi_instance_id="ci",
                           glpi_entity_id="7", incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1)
        self.core = {"run": {"run_id": "RUN-12345678",
                             "incident_id": "INC-DEMO-12345678", "mode": "DEMO"}}
        self.glpi = {"id": 201, "entities_id": 7, "name": "example"}

    def fetch(self, **kwargs):
        self.calls.append("fetch")
        return {"fixture": "not-a-real-signature"}

    def verify(self, **kwargs):
        self.calls.append("verify")
        return dict(self.claims)

    def core_reader(self, **kwargs):
        self.calls.append("core")
        return self.core

    def glpi_reader(self, **kwargs):
        self.calls.append("glpi")
        return self.glpi

    def invoke(self, **kwargs):
        args = dict(actor="operator", tenant_id="tenant-a", ticket_id="201",
                    fetch_signed_event=self.fetch,
                    verify_event_and_acl=self.verify,
                    read_core_raw=self.core_reader, read_glpi_raw=self.glpi_reader)
        args.update(kwargs)
        return qualify_raw_glpi_core_readbacks(**args)

    def test_uninstalled_verifier_prevents_all_upstream_reads(self):
        with self.assertRaises(GLPIRawQualificationBlocked):
            self.invoke(verify_event_and_acl=None)
        self.assertEqual(self.calls, [])

    def test_uninstalled_raw_reader_prevents_xref_lookup(self):
        with self.assertRaises(GLPIRawQualificationBlocked):
            self.invoke(read_glpi_raw=None)
        self.assertEqual(self.calls, [])

    def test_order_and_read_only_output_with_fake_verifier(self):
        result = self.invoke()
        self.assertEqual(self.calls, ["fetch", "verify", "core", "glpi"])
        self.assertEqual(result["status"], "RAW_READBACKS_MATCH_SIGNED_XREF_CLAIMS")
        self.assertEqual(result["run_id"], "RUN-12345678")
        self.assertFalse(result["copilot_query_performed"])
        self.assertFalse(result["hitl_proposal_created"])
        self.assertFalse(result["glpi_write_performed"])
        self.assertFalse(result["execution_allowed"])

    def test_core_incident_mismatch_fails_closed(self):
        self.core["run"]["incident_id"] = "INC-OTHER-12345678"
        with self.assertRaises(GLPIRawQualificationBlocked):
            self.invoke()

    def test_glpi_entity_mismatch_fails_closed(self):
        self.glpi["entities_id"] = 8
        with self.assertRaises(GLPIRawQualificationBlocked):
            self.invoke()

    def test_boolean_verifier_does_not_authorize_read(self):
        with self.assertRaises(GLPIRawQualificationBlocked):
            self.invoke(verify_event_and_acl=lambda **_: True)
        self.assertEqual(self.calls, ["fetch"])


if __name__ == "__main__":
    unittest.main()
