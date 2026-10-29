"""No-effect presentation contract tests; no Core, GLPI or Temporal I/O."""
import copy
import unittest

from app.shared.acme_policy_demo_result import present_demo_policy_result


def receipt(status="SIMULATED_SUCCESS", gate_status="SIMULATED"):
    before = {"target_ci": "ACME-LNX-01", "health": "DEGRADED", "service_available": False}
    after = {"target_ci": "ACME-LNX-01", "health": "HEALTHY", "service_available": True} if status == "SIMULATED_SUCCESS" else dict(before)
    return {
        "schema": "aiops.acme-remediation-receipt.v1", "classification": "SYNTHETIC_UNVERIFIED",
        "run_id": "RUN-ACME-OFFLINE-001", "scenario_id": "SCN-ACME-OFFLINE",
        "evidence_ids": ["EVD-ACME-OFFLINE-1"], "receipt_digest": "a" * 64,
        "core_run_verified": False, "evidence_verified": False, "effect_applied": False, "persisted": False,
        "projection": {
            "mode": "DEMO", "status": status, "recipe_id": "ansible-service-restart",
            "target_ci": "ACME-LNX-01", "proposal_digest": "b" * 64,
            "effect_applied": False, "postchecks": "NOT_RUN", "before": before, "after": after,
            "rollback": {"status": "PROJECTED_ONLY", "effect_applied": False},
            "gate": {"mode": "DEMO", "status": gate_status, "target_ci": "ACME-LNX-01", "proposal_digest": "b" * 64},
        },
    }


class PolicyDemoResultTests(unittest.TestCase):
    def test_simulate_is_explicitly_not_authenticated_or_executed(self):
        result = present_demo_policy_result(receipt())
        self.assertEqual(result["policy"]["decision"], "SIMULATE")
        self.assertEqual(result["human"]["status"], "APPROVAL_FIXTURE_ONLY")
        self.assertFalse(result["human"]["authenticated_runtime"])
        self.assertFalse(result["effect_applied"])
        self.assertFalse(result["evidence"]["core_verified"])
        self.assertFalse(result["before_after"]["observed"])
        self.assertEqual(result["before_after"]["after_hypothesis"]["health"], "HEALTHY")
        self.assertTrue(result["rollback"]["projected_only"])

    def test_blocked_is_not_simulate(self):
        result = present_demo_policy_result(receipt("BLOCKED", "BLOCKED"))
        self.assertEqual(result["policy"]["decision"], "BLOCKED")
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertEqual(result["before_after"]["before"], result["before_after"]["after_hypothesis"])

    def test_failure_is_hypothetical(self):
        result = present_demo_policy_result(receipt("SIMULATED_FAILURE"))
        self.assertEqual(result["policy"]["decision"], "SIMULATE")
        self.assertFalse(result["effect_applied"])

    def test_live_mode_rejected(self):
        r = receipt(); r["projection"]["mode"] = "LIVE"; r["projection"]["gate"]["mode"] = "LIVE"
        with self.assertRaisesRegex(ValueError, "mode_not_demo"):
            present_demo_policy_result(r)

    def test_false_attestation_rejected(self):
        for key in ("core_run_verified", "evidence_verified", "effect_applied", "persisted"):
            with self.subTest(key=key):
                r = receipt(); r[key] = True
                with self.assertRaisesRegex(ValueError, "receipt_attestation_claim_forbidden"):
                    present_demo_policy_result(r)

    def test_forged_gate_success_rejected(self):
        with self.assertRaisesRegex(ValueError, "projection_gate_inconsistent"):
            present_demo_policy_result(receipt("SIMULATED_SUCCESS", "BLOCKED"))

    def test_snapshot_target_mismatch_rejected(self):
        r = receipt(); r["projection"]["after"]["target_ci"] = "ACME-SAN-FABRIC-A"
        with self.assertRaisesRegex(ValueError, "snapshot_binding_invalid"):
            present_demo_policy_result(r)

    def test_rollback_execution_claim_rejected(self):
        r = receipt(); r["projection"]["rollback"]["effect_applied"] = True
        with self.assertRaisesRegex(ValueError, "rollback_effect_claim_forbidden"):
            present_demo_policy_result(r)

    def test_real_receipt_builder_success_and_failure(self):
        """Exercise the existing receipt -> projection -> local gate -> presentation chain."""
        from app.shared.acme_demo_offline import demo_receipt

        for outcome, expected in (("SUCCESS", "SIMULATED_SUCCESS"), ("FAILURE", "SIMULATED_FAILURE")):
            with self.subTest(outcome=outcome):
                source = demo_receipt(outcome)
                self.assertEqual(source["projection"]["status"], expected)
                result = present_demo_policy_result(source)
                self.assertEqual(result["policy"]["decision"], "SIMULATE")
                self.assertEqual(result["classification"], "SIMULATED")
                self.assertEqual(result["run_id"], source["run_id"])
                self.assertEqual(result["evidence"]["ids"], source["evidence_ids"])
                self.assertEqual(result["evidence"]["receipt_digest"], source["receipt_digest"])
                self.assertEqual(result["human"]["status"], "APPROVAL_FIXTURE_ONLY")
                self.assertFalse(result["human"]["authenticated_runtime"])
                self.assertFalse(result["policy"]["core_policy_verified"])
                self.assertFalse(result["before_after"]["observed"])
                self.assertFalse(result["rollback"]["executed"])
                self.assertFalse(result["effect_applied"])
                self.assertFalse(result["persisted"])

    def test_real_receipt_builder_blocked_decision_not_approved(self):
        """The receipt builder must not be bypassed by a forged approved-looking fixture."""
        from app.shared.acme_demo_offline import demo_receipt

        source = demo_receipt("SUCCESS")
        source["projection"]["gate"]["status"] = "BLOCKED"
        with self.assertRaisesRegex(ValueError, "projection_gate_inconsistent"):
            present_demo_policy_result(source)

    def test_does_not_mutate_input(self):
        r = receipt(); before = copy.deepcopy(r)
        present_demo_policy_result(r)
        self.assertEqual(r, before)


if __name__ == "__main__":
    unittest.main()
