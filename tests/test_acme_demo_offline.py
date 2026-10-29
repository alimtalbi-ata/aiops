"""Contract tests for reproducible offline ACME demonstration fixtures."""
import unittest
from app.shared.acme_demo_offline import demo_receipt


class OfflineDemoTests(unittest.TestCase):
    def test_success_fixture_is_explicitly_unverified(self):
        result = demo_receipt("SUCCESS")
        self.assertEqual(result["schema"], "aiops.acme-remediation-receipt.v1")
        self.assertEqual(result["projection"]["status"], "SIMULATED_SUCCESS")
        self.assertEqual(result["projection"]["before"]["health"], "DEGRADED")
        self.assertEqual(result["projection"]["after"]["health"], "HEALTHY")
        self.assertFalse(result["effect_applied"])
        self.assertFalse(result["persisted"])
        self.assertFalse(result["evidence_verified"])
        self.assertFalse(result["core_run_verified"])
        self.assertEqual(result["projection"]["postchecks"], "NOT_RUN")
        self.assertNotIn("vault://", str(result))

    def test_failure_fixture_keeps_original_state(self):
        result = demo_receipt("FAILURE")
        self.assertEqual(result["projection"]["status"], "SIMULATED_FAILURE")
        self.assertEqual(result["projection"]["before"], result["projection"]["after"])
        self.assertEqual(result["projection"]["rollback"]["status"], "PROJECTED_ONLY")

    def test_deterministic_receipts(self):
        self.assertEqual(demo_receipt("SUCCESS"), demo_receipt("SUCCESS"))
        self.assertNotEqual(demo_receipt("SUCCESS")["receipt_digest"], demo_receipt("FAILURE")["receipt_digest"])

    def test_unknown_outcome_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported_outcome"):
            demo_receipt("EXECUTE")


if __name__ == "__main__":
    unittest.main()
