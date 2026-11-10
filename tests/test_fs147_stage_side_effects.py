"""FS147 stage side-effect claims must stop read-only pipeline progression."""
import unittest
from datetime import datetime, timezone

from worker.fs147_readonly_pipeline import FS147Request, execute


class StageEffectsTests(unittest.TestCase):
    def setUp(self):
        self.req = FS147Request("tenant", "actor", "incident", "run")
        self.calls = []
        self.scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                          run_id="run", ticket_id=147, evidence_id="ev-1")
        self.clock = lambda: datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)

    def observe(self, _):
        self.calls.append("observe")
        return dict(self.scope, source="fs-lab-bridge-readonly",
                    commands=["df", "du", "ls"], filesystem="/fs-lab",
                    read_only=True, collected_at="2026-11-10T01:00:00+00:00",
                    used_percent=50)

    def analyst(self, _, observation):
        self.calls.append("analyst")
        return dict(self.scope, findings=["fs-lab diagnostic"])

    def critic(self, *_):
        self.calls.append("critic")
        return dict(self.scope, state="PASS", validated=True,
                    missing_information=[])

    def policy(self, *_):
        self.calls.append("policy")
        return dict(self.scope, state="PASS", decision="SIMULATE",
                    dispatch_allowed=False, effect="NO_EFFECT")

    def run_case(self, analyst=None, critic=None):
        return execute(self.req, stop_auto=False, observe=self.observe,
                       analyst=analyst or self.analyst, critic=critic or self.critic,
                       policy=self.policy, claim_once=lambda _: True, now=self.clock)

    def test_analyst_claims_block_before_critic_and_policy(self):
        for field, value in (("action_executed", True), ("remediation_executed", True),
                             ("mutation_performed", 1), ("ticket_transition", "RESOLVED"),
                             ("dispatch_allowed", True), ("resolved", True),
                             ("effect", "MUTATED")):
            with self.subTest(field=field):
                self.calls = []
                def altered(request, observation):
                    return dict(self.analyst(request, observation), **{field: value})
                result = self.run_case(analyst=altered)
                self.assertEqual((result["status"], result["reason"], result["effect"]),
                                 ("BLOCKED", "ANALYST_SIDE_EFFECT", "NO_EFFECT"))
                self.assertEqual(self.calls, ["observe", "analyst"])

    def test_critic_claims_block_before_policy(self):
        for field, value in (("action_executed", True), ("remediation_executed", True),
                             ("mutation_performed", "yes"), ("ticket_transition", "RESOLVED"),
                             ("dispatch_allowed", True), ("resolved", True),
                             ("effect", "LIVE")):
            with self.subTest(field=field):
                self.calls = []
                def altered(*args):
                    return dict(self.critic(*args), **{field: value})
                result = self.run_case(critic=altered)
                self.assertEqual((result["status"], result["reason"], result["effect"]),
                                 ("BLOCKED", "CRITIC_SIDE_EFFECT", "NO_EFFECT"))
                self.assertEqual(self.calls, ["observe", "analyst", "critic"])

    def test_clean_readonly_path_and_duplicate_claim(self):
        result = self.run_case()
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertEqual(self.calls, ["observe", "analyst", "critic", "policy"])
        self.calls = []
        duplicate = execute(self.req, stop_auto=False, observe=self.observe,
                            analyst=self.analyst, critic=self.critic,
                            policy=self.policy, claim_once=lambda _: False, now=self.clock)
        self.assertEqual(duplicate["reason"], "DUPLICATE_RUN")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
