"""Synthetic autonomous loop must never imply live execution or learning."""
import unittest
from scripts.acme_autonomous_loop_qualification import assess_autonomous_loop, STAGES
from test_acme_core_worker_binding import pair


class AutonomousLoopTests(unittest.TestCase):
    def test_complete_synthetic_loop_is_not_runtime_go(self):
        core, worker = pair()
        result = assess_autonomous_loop(core, worker)
        self.assertEqual(result["status"], "OFFLINE_CONSISTENT_ONLY")
        self.assertEqual(result["reason"], "NO_RUNTIME_ATTESTATION")
        self.assertTrue(all(result["stages"][stage] == "OFFLINE_DECLARED_ONLY"
                            for stage in STAGES if stage not in ("REMEDIATION_EFFECT", "LEARN")))
        self.assertEqual(result["stages"]["REMEDIATION_EFFECT"], "NOT_VERIFIED")
        self.assertEqual(result["stages"]["LEARN"], "NOT_VERIFIED")
        self.assertEqual(result["action_semantics"], "WORKER_SIMULATED_NO_EFFECT_PRE_RESOLUTION")
        self.assertEqual(result["verification_semantics"], "CORE_SYNTHETIC_RESOLUTION_DECLARED")
        self.assertEqual(result["audit_semantics"], "WORKER_TEMPORAL_HISTORY_DECLARED_NOT_ATTESTED")
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["real_execution_allowed"])
        self.assertFalse(result["learning_claim_verified"])

    def test_broken_transition_order_is_rejected(self):
        core, worker = pair()
        worker["audit_transitions"] = list(reversed(worker["audit_transitions"]))
        result = assess_autonomous_loop(core, worker)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("WORKER_TRANSITIONS_INVALID", result["rejection_codes"])

    def test_missing_post_action_verification_is_rejected(self):
        core, worker = pair()
        core["resolution_after_worker_receipt"] = False
        result = assess_autonomous_loop(core, worker)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("CORE_RESOLUTION_AFTER_WORKER_RECEIPT_NOT_VERIFIED",
                      result["rejection_codes"])

    def test_unconsumed_approval_nonce_is_rejected(self):
        core, worker = pair()
        core["approval_nonce_consumed"] = False
        result = assess_autonomous_loop(core, worker)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("CORE_APPROVAL_NONCE_CONSUMED_NOT_VERIFIED",
                      result["rejection_codes"])

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
