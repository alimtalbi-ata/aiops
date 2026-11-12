"""Workflow short-circuit tests: no downstream service on refusal or duplicate.

These use fakes only; they do not certify a live fs-lab bridge.
"""
import unittest

from worker.fs147_readonly_pipeline import FS147Request, execute

REQUEST = FS147Request("tenant", "actor", "incident", "run")


def scoped(**extra):
    return dict(tenant_id="tenant", incident_id="incident",
                run_id="run", ticket_id=147, evidence_id="ev", **extra)


def observed(_):
    return scoped(source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                  read_only=True, filesystem="/fs-lab", used_percent=92,
                  collected_at="2026-11-06T00:00:00Z")


class ShortCircuitTests(unittest.TestCase):
    def invoke(self, *, stop=False, claim=True, observation=None,
               analysis=None, critique=None, decision=None):
        called = []
        def wrap(name, result):
            def callback(*args):
                called.append(name)
                return result(*args) if callable(result) else result
            return callback
        outcome = execute(
            REQUEST, stop_auto=stop,
            claim_once=wrap("CLAIM", lambda _: claim),
            observe=wrap("OBSERVE", observed if observation is None else observation),
            analyst=wrap("ANALYST", scoped(findings=["measurement"]) if analysis is None else analysis),
            critic=wrap("CRITIC", scoped(state="PASS") if critique is None else critique),
            policy=wrap("POLICY", scoped(state="PASS", decision="SIMULATE") if decision is None else decision),
        )
        self.assertFalse(outcome["resolved"])
        self.assertEqual(outcome["effect"], "NO_EFFECT")
        return outcome, called

    def test_stop_auto_prevents_every_adapter(self):
        result, calls = self.invoke(stop=True)
        self.assertEqual(result["reason"], "STOP_AUTO")
        self.assertEqual(calls, [])

    def test_duplicate_prevents_observation_and_agents(self):
        result, calls = self.invoke(claim=False)
        self.assertEqual(result["reason"], "DUPLICATE_RUN")
        self.assertEqual(calls, ["CLAIM"])

    def test_insufficient_observation_prevents_agents(self):
        result, calls = self.invoke(observation=scoped(
            source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
            read_only=True, filesystem="/fs-lab", collected_at="now"))
        self.assertEqual(result["reason"], "INSUFFICIENT_OBSERVATION")
        self.assertEqual(calls, ["CLAIM", "OBSERVE"])

    def test_insufficient_analysis_prevents_critic_and_policy(self):
        result, calls = self.invoke(analysis=scoped(findings=[]))
        self.assertEqual(result["reason"], "INSUFFICIENT_ANALYSIS")
        self.assertEqual(calls, ["CLAIM", "OBSERVE", "ANALYST"])

    def test_critic_refusal_prevents_policy(self):
        result, calls = self.invoke(critique=scoped(state="BLOCKED"))
        self.assertEqual(result["reason"], "CRITIC_REFUSED")
        self.assertEqual(calls, ["CLAIM", "OBSERVE", "ANALYST", "CRITIC"])

    def test_policy_refusal_does_not_resolve(self):
        result, calls = self.invoke(decision=scoped(state="PASS", decision="DENY"))
        self.assertEqual(result["reason"], "POLICY_REFUSED")
        self.assertEqual(calls, ["CLAIM", "OBSERVE", "ANALYST", "CRITIC", "POLICY"])

    def test_success_remains_no_effect(self):
        result, calls = self.invoke()
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertEqual(calls, ["CLAIM", "OBSERVE", "ANALYST", "CRITIC", "POLICY"])


if __name__ == "__main__":
    unittest.main()
