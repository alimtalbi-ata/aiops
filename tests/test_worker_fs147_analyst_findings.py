"""Reject insufficient Analyst output before Critic or Policy can run."""
import unittest
from worker.fs147_readonly_pipeline import execute
from test_worker_fs147_readonly_pipeline import R, observation, scoped


class AnalystInsufficiencyTests(unittest.TestCase):
    def test_malformed_findings_short_circuit(self):
        for findings in (None, "", "looks fine", [], [""], ["  "], [None], [42], ["valid", ""]):
            with self.subTest(findings=findings):
                called = []
                def critic(*args):
                    called.append("critic")
                    raise AssertionError("Critic must not run")
                def policy(*args):
                    called.append("policy")
                    raise AssertionError("Policy must not run")
                result = execute(
                    R, stop_auto=False, observe=observation,
                    analyst=lambda *args, f=findings: scoped(findings=f),
                    critic=critic, policy=policy, claim_once=lambda _: True)
                self.assertEqual(result["reason"], "INSUFFICIENT_ANALYSIS")
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertFalse(result["resolved"])
                self.assertEqual(called, [])
                self.assertEqual(result["steps"], ["OBSERVE"])

    def test_valid_findings_reach_real_policy_adapter(self):
        called = []
        def critic(*args):
            called.append("critic")
            return scoped(state="PASS")
        def policy(*args):
            called.append("policy")
            return scoped(state="PASS", decision="DENY")
        result = execute(
            R, stop_auto=False, observe=observation,
            analyst=lambda *args: scoped(findings=["df and du measurements"]),
            critic=critic, policy=policy, claim_once=lambda _: True)
        self.assertEqual(called, ["critic", "policy"])
        self.assertEqual(result["reason"], "POLICY_REFUSED")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])


if __name__ == "__main__":
    unittest.main()
