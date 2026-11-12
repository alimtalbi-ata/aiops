"""Bound Analyst payload before forwarding to Critic (no IO)."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

class AnalystBudgetTests(unittest.TestCase):
    def run_case(self, findings):
        req = FS147Request("tenant", "actor", "incident", "run")
        now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        identity = dict(tenant_id="tenant", actor_id="actor",
                        incident_id="incident", run_id="run", ticket_id=147)
        observation = dict(identity, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="ev1",
                           collected_at=now.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        calls = []
        def critic(*args):
            calls.append("critic")
            return dict(identity, evidence_id="ev1", state="BLOCKED")
        result = execute(req, stop_auto=False, observe=lambda _: observation,
                         analyst=lambda *_: dict(identity, evidence_id="ev1", findings=findings),
                         critic=critic, policy=lambda *_: self.fail("Policy must not run"),
                         claim_once=lambda _: True, now=lambda: now)
        return result, calls

    def test_rejects_more_than_64_findings_before_critic(self):
        result, calls = self.run_case(["evidence"] * 65)
        self.assertEqual(result["reason"], "INSUFFICIENT_ANALYSIS")
        self.assertEqual(calls, [])

    def test_rejects_oversized_finding_before_critic(self):
        result, calls = self.run_case(["x" * 2049])
        self.assertEqual(result["reason"], "INSUFFICIENT_ANALYSIS")
        self.assertEqual(calls, [])

    def test_boundary_reaches_critic_but_not_policy(self):
        result, calls = self.run_case(["x" * 2048] * 64)
        self.assertEqual(result["reason"], "CRITIC_REFUSED")
        self.assertEqual(calls, ["critic"])

if __name__ == "__main__":
    unittest.main()
