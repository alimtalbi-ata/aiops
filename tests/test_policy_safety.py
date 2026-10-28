import unittest

from app.policy.main import Decision, evaluate


def decision(**overrides):
    values = {
        "mode": "LIVE",
        "command": "EXECUTE",
        "severity": "P2",
        "confidence": 0.99,
        "evidence_count": 2,
        "critic_validated": True,
        "redundancy_ok": True,
        "evidence_fresh": True,
        "preconditions_verified": True,
        "fencing_verified": True,
        "human_approved": True,
    }
    values.update(overrides)
    return Decision(**values)


class PolicySafetyTests(unittest.TestCase):
    def test_p1_is_always_escalated_even_with_all_proofs(self):
        result = evaluate(decision(severity="P1"))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_p1_without_evidence_still_escalates(self):
        result = evaluate(decision(severity="P1", evidence_count=0))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_missing_evidence_is_unknown_for_non_p1(self):
        result = evaluate(decision(evidence_count=0))
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["decision"], "HUMAN_APPROVAL")

    def test_live_missing_fencing_is_blocked(self):
        result = evaluate(decision(fencing_verified=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("fencing", result["reason"])

    def test_live_effect_without_human_approval_is_blocked(self):
        result = evaluate(decision(human_approved=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("human approval", result["reason"])

    def test_live_p2_observe_with_all_required_proofs_can_pass_policy(self):
        result = evaluate(decision(command="OBSERVE"))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "ALLOW")

    def test_live_effect_with_boolean_approval_cannot_pass(self):
        for command in ("EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"):
            with self.subTest(command=command):
                result = evaluate(decision(command=command, human_approved=True))
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["decision"], "HUMAN_APPROVAL")
                self.assertIn("one-use HITL binding", result["reason"])

    def test_live_cancel_without_human_approval_is_blocked(self):
        result = evaluate(decision(command="CANCEL", human_approved=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("human approval", result["reason"])

    def test_live_enrich_with_all_required_proofs_can_pass_policy(self):
        result = evaluate(decision(command="ENRICH", human_approved=False))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "ALLOW")

    def test_other_synthetic_modes_never_allow_live_effect(self):
        for mode in ("REPLAY", "STORY"):
            with self.subTest(mode=mode):
                result = evaluate(decision(mode=mode, command="REMEDIATE"))
                self.assertEqual(result["decision"], "SIMULATE")

    def test_demo_is_simulation_only(self):
        result = evaluate(decision(mode="DEMO", human_approved=False))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "SIMULATE")


if __name__ == "__main__":
    unittest.main()
