"""Negative actor-binding tests for FS147 read-only workflow.

Fakes are deliberately not claims of live bridge/Policy qualification.
"""
import unittest
from worker.fs147_readonly_pipeline import FS147Request, execute

REQUEST = FS147Request("tenant", "actor-147", "incident-147", "run-147")


def scoped(**fields):
    return dict(tenant_id="tenant", incident_id="incident-147",
                run_id="run-147", ticket_id=147, evidence_id="evidence-147",
                **fields)


class ActorBindingTests(unittest.TestCase):
    def run_with_actor(self, stage):
        calls = []

        def observe(req):
            calls.append("OBSERVE")
            return scoped(source="fs-lab-bridge-readonly",
                          commands=["df", "du", "ls"], read_only=True,
                          filesystem="/fs-lab", used_percent=92,
                          collected_at="2026-11-06T04:00:00Z",
                          actor_id="other-actor" if stage == "OBSERVE" else "actor-147")

        def analyst(req, observation):
            calls.append("ANALYST")
            return scoped(findings=["lab disk usage"],
                          actor_id="other-actor" if stage == "ANALYST" else "actor-147")

        def critic(req, observation, analysis):
            calls.append("CRITIC")
            return scoped(state="PASS",
                          actor_id="other-actor" if stage == "CRITIC" else "actor-147")

        def policy(req, observation, analysis, critique):
            calls.append("POLICY")
            return scoped(state="PASS", decision="SIMULATE",
                          actor_id="other-actor" if stage == "POLICY" else "actor-147")

        result = execute(REQUEST, stop_auto=False, claim_once=lambda key: True,
                         observe=observe, analyst=analyst, critic=critic, policy=policy)
        return result, calls

    def test_observation_from_other_actor_stops_agents(self):
        result, calls = self.run_with_actor("OBSERVE")
        self.assertEqual((result["status"], result["reason"]), ("BLOCKED", "OBSERVATION_SCOPE"))
        self.assertEqual(calls, ["OBSERVE"])
        self.assertFalse(result["resolved"])

    def test_analysis_from_other_actor_stops_critic(self):
        result, calls = self.run_with_actor("ANALYST")
        self.assertEqual((result["status"], result["reason"]), ("BLOCKED", "ANALYST_SCOPE"))
        self.assertEqual(calls, ["OBSERVE", "ANALYST"])

    def test_critic_from_other_actor_stops_policy(self):
        result, calls = self.run_with_actor("CRITIC")
        self.assertEqual((result["status"], result["reason"]), ("BLOCKED", "CRITIC_SCOPE"))
        self.assertEqual(calls, ["OBSERVE", "ANALYST", "CRITIC"])

    def test_policy_from_other_actor_cannot_authorize(self):
        result, calls = self.run_with_actor("POLICY")
        self.assertEqual((result["status"], result["reason"]), ("BLOCKED", "POLICY_SCOPE"))
        self.assertEqual(calls, ["OBSERVE", "ANALYST", "CRITIC", "POLICY"])
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])

    def test_same_actor_simulation_is_no_effect(self):
        result, calls = self.run_with_actor(None)
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(calls, ["OBSERVE", "ANALYST", "CRITIC", "POLICY"])


if __name__ == "__main__":
    unittest.main()
