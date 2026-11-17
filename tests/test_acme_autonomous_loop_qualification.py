"""Synthetic autonomous loop must never imply live execution or learning."""
import unittest
from scripts.acme_autonomous_loop_qualification import assess_autonomous_loop, STAGES


class AutonomousLoopTests(unittest.TestCase):
    def test_missing_receipts_fail_closed(self):
        result = assess_autonomous_loop(None, None)
        self.assertEqual(result["status"], "NO_GO")
        self.assertFalse(result["real_execution_allowed"])
        self.assertFalse(result["learning_claim_verified"])
        self.assertEqual(set(result["stages"]), set(STAGES))

    def test_untrusted_receipts_cannot_grant_execution(self):
        result = assess_autonomous_loop(
            {"schema": "aiops.core-acme-sandbox-readback.v1",
             "execution_allowed": True, "effect_allowed": True},
            {"schema": "aiops.worker-acme-simulated-no-effect.v1",
             "effect_allowed": True})
        self.assertEqual(result["status"], "NO_GO")
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["real_execution_allowed"])
        self.assertTrue(result["rejection_codes"])

    def test_forged_matching_ids_cannot_qualify(self):
        core = {"tenant_id": "ACME-TEST", "attempt_id": "ACME-SIM-1234567890ABCDEF",
                "run_id": "RUN-SIM-AAAAAAAAAAAAAAAAAAAAAAAA"}
        worker = dict(core)
        result = assess_autonomous_loop(core, worker)
        self.assertEqual(result["status"], "NO_GO")
        self.assertFalse(result["learning_claim_verified"])


if __name__ == "__main__":
    unittest.main()
