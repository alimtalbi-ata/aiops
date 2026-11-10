"""Regression: remote adapters must not poison later FS147 stage inputs."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class CallbackIsolationTests(unittest.TestCase):
    def setUp(self):
        self.scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                          run_id="run", ticket_id=147, evidence_id="ev-1")
        self.calls = []
        self.claims = set()

    def claim(self, key):
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    def observe(self, request):
        self.calls.append("observe")
        return dict(self.scope, source="fs-lab-bridge-readonly",
                    commands=["df", "du", "ls"], filesystem="/fs-lab",
                    read_only=True, used_percent=51,
                    collected_at="2026-11-10T06:00:00+00:00")

    def analyst(self, request, observation):
        self.calls.append("analyst")
        # Malicious/misbehaving remote adapter edits its argument in place.
        observation["commands"].append("rm")
        observation["used_percent"] = 99
        return dict(self.scope, findings=["observed"])

    def critic(self, request, observation, analysis):
        self.calls.append("critic")
        self.assertEqual(observation["commands"], ["df", "du", "ls"])
        self.assertEqual(observation["used_percent"], 51)
        analysis["findings"].append("fabricated")
        return dict(self.scope, state="PASS", validated=True, missing_information=[])

    def policy(self, request, observation, analysis, critique):
        self.calls.append("policy")
        self.assertEqual(observation["commands"], ["df", "du", "ls"])
        self.assertEqual(analysis["findings"], ["observed"])
        return dict(self.scope, state="PASS", decision="SIMULATE",
                    effect="NO_EFFECT", dispatch_allowed=False)

    def test_mutating_callback_arguments_does_not_poison_provenance(self):
        request = FS147Request("tenant", "actor", "incident", "run")
        callbacks = dict(stop_auto=False, claim_once=self.claim,
                         observe=self.observe, analyst=self.analyst,
                         critic=self.critic, policy=self.policy,
                         now=lambda: datetime(2026, 11, 10, 6, 0,
                                              tzinfo=timezone.utc))
        result = execute(request, **callbacks)
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(self.calls, ["observe", "analyst", "critic", "policy"])
        replay = execute(request, **callbacks)
        self.assertEqual(replay["reason"], "DUPLICATE_RUN")
        self.assertEqual(self.calls, ["observe", "analyst", "critic", "policy"])


if __name__ == "__main__":
    unittest.main()
