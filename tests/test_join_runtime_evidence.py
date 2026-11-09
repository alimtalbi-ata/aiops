"""Integration joiner tests: independent receipts, correlation, provenance and GLPI."""
import unittest
from ops.coordination.join_runtime_evidence import join, SOURCES

def valid():
    return {source: {"correlation_id": "incident-123",
                     "source_provenance": "REAL",
                     "evidence_ref": "github://verified-source/" + source,
                     "status": expected}
            for source, (_, expected) in SOURCES.items()}

class RuntimeEvidenceTests(unittest.TestCase):
    def test_complete_independent_receipts(self):
        self.assertEqual(join(valid(), "incident-123"),
                         {"status": "PASS", "reasons": []})

    def test_missing_each_source_holds(self):
        for source in SOURCES:
            with self.subTest(source=source):
                receipts = valid()
                del receipts[source]
                self.assertEqual(join(receipts, "incident-123")["status"], "HOLD")

    def test_mismatched_correlation_holds(self):
        receipts = valid()
        receipts["glpi"]["correlation_id"] = "other"
        self.assertIn("CORRELATION_MISMATCH_GLPI",
                      join(receipts, "incident-123")["reasons"])

    def test_synthetic_source_holds(self):
        receipts = valid()
        receipts["core"]["source_provenance"] = "SYNTHETIC"
        self.assertIn("UNVERIFIED_PROVENANCE_CORE",
                      join(receipts, "incident-123")["reasons"])

    def test_missing_evidence_ref_holds(self):
        receipts = valid()
        receipts["worker"].pop("evidence_ref")
        self.assertIn("MISSING_EVIDENCE_REF_WORKER",
                      join(receipts, "incident-123")["reasons"])

    def test_glpi_readback_unverified_holds(self):
        receipts = valid()
        receipts["itsm"]["status"] = "UNVERIFIED"
        self.assertIn("INVALID_ITSM_READBACK",
                      join(receipts, "incident-123")["reasons"])

    def test_policy_rejected_holds(self):
        receipts = valid()
        receipts["policy"]["status"] = "REJECTED"
        self.assertIn("INVALID_POLICY_STATUS",
                      join(receipts, "incident-123")["reasons"])

    def test_no_correlation_holds(self):
        self.assertEqual(join(valid(), "")["status"], "HOLD")

if __name__ == "__main__":
    unittest.main()
