"""Regression: FS147 observation may expire during a slow remote Policy call."""
import unittest
from datetime import datetime, timedelta, timezone

from worker.fs147_readonly_pipeline import FS147Request, execute


class PostPolicyFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.request = FS147Request("tenant", "actor", "incident", "run")
        self.start = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
        self.base = dict(tenant_id="tenant", actor_id="actor",
                         incident_id="incident", run_id="run", ticket_id=147)
        self.observation = dict(self.base, source="fs-lab-bridge-readonly",
                                commands=["df", "du", "ls"], evidence_id="evidence-1",
                                collected_at=self.start.isoformat(), used_percent=92,
                                filesystem="/fs-lab", read_only=True)

    def run_case(self, times, critic_state="PASS"):
        # Clock now checked after observation and after Analyst before Critic.
        calls = iter([times[0], times[0], *times[1:]] )
        policy_calls = []
        def analyst(req, obs):
            return dict(self.base, evidence_id="evidence-1", findings=["usage high"])
        def critic(req, obs, analysis):
            return dict(self.base, evidence_id="evidence-1", state=critic_state)
        def policy(req, obs, analysis, critique):
            policy_calls.append(True)
            return dict(self.base, evidence_id="evidence-1",
                        state="PASS", decision="SIMULATE")
        result = execute(self.request, stop_auto=False,
                         observe=lambda req: self.observation,
                         analyst=analyst, critic=critic, policy=policy,
                         claim_once=lambda key: True, now=lambda: next(calls))
        return result, policy_calls

    def test_policy_latency_expires_observation(self):
        result, calls = self.run_case([
            self.start + timedelta(minutes=4),
            self.start + timedelta(minutes=4, seconds=30),
            self.start + timedelta(minutes=5, seconds=1),
        ])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "STALE_OBSERVATION")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertEqual(len(calls), 1)

    def test_policy_within_freshness_window(self):
        result, calls = self.run_case([
            self.start + timedelta(minutes=4),
            self.start + timedelta(minutes=4, seconds=30),
            self.start + timedelta(minutes=5),
        ])
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(len(calls), 1)

    def test_analyst_latency_expires_before_critic(self):
        critic_calls = []
        base = dict(self.base, evidence_id="evidence-1")
        def analyst(req, obs):
            return dict(base, findings=["usage high"])
        def critic(req, obs, analysis):
            critic_calls.append(True)
            return dict(base, state="PASS")
        result = execute(self.request, stop_auto=False,
                         observe=lambda req: self.observation,
                         analyst=analyst, critic=critic,
                         policy=lambda *args: self.fail("Policy must not run"),
                         claim_once=lambda key: True,
                         now=iter([self.start + timedelta(minutes=4),
                                   self.start + timedelta(minutes=5, seconds=1)]).__next__)
        self.assertEqual(result["reason"], "STALE_OBSERVATION")
        self.assertEqual(result["steps"], ["OBSERVE", "ANALYST"])
        self.assertEqual(critic_calls, [])

    def test_critic_refusal_does_not_call_policy(self):
        result, calls = self.run_case([self.start + timedelta(minutes=4)],
                                      critic_state="BLOCKED")
        self.assertEqual(result["reason"], "CRITIC_REFUSED")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
