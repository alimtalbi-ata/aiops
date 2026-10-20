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

    def test_live_p2_with_all_required_proofs_can_pass_policy(self):
        result = evaluate(decision())
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "ALLOW")

    def test_demo_is_simulation_only(self):
        result = evaluate(decision(mode="DEMO", human_approved=False))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "SIMULATE")



    def test_demo_rejected_critic_is_blocked(self):
        output=evaluate(decision(mode="DEMO",critic_validated=False))
        self.assertEqual(output["state"],"BLOCKED")
        self.assertEqual(output["decision"],"HUMAN_APPROVAL")

    def test_demo_stale_evidence_must_not_simulate_a_success(self):
        output=evaluate(decision(mode="DEMO",evidence_fresh=False))
        self.assertEqual(output["state"],"BLOCKED")
        self.assertEqual(output["decision"],"ENRICH")

    def test_demo_unknown_severity_requires_enrichment(self):
        output=evaluate(decision(mode="DEMO",severity="UNKNOWN"))
        self.assertEqual(output["state"],"UNKNOWN")
        self.assertEqual(output["decision"],"ENRICH")

    def test_demo_low_confidence_does_not_pass(self):
        output=evaluate(decision(mode="DEMO",confidence=.2))
        self.assertEqual(output["state"],"BLOCKED")

    def test_live_unknown_severity_cannot_allow_effects(self):
        output=evaluate(decision(severity="UNKNOWN"))
        self.assertEqual(output["state"],"UNKNOWN")
        self.assertNotEqual(output["decision"],"ALLOW")

    def test_simulated_p1_can_pass_only_as_simulation(self):
        output=evaluate(decision(mode="DEMO",severity="P1"))
        self.assertEqual(output["state"],"PASS")
        self.assertEqual(output["decision"],"SIMULATE")

if __name__ == "__main__":
    unittest.main()
