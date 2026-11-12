"""FS147 fail-closed contract regression; no host access or ticket mutation."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


NOW = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "worker", "incident-147", "run-147")


def scoped(**fields):
    return dict(tenant_id=REQ.tenant_id, actor_id=REQ.actor_id,
                incident_id=REQ.incident_id, run_id=REQ.run_id,
                ticket_id=147, **fields)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.claimed = set()

    def claim(self, key):
        self.calls.append("claim")
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True

    def observe(self, request):
        self.calls.append("bridge")
        return scoped(source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                      evidence_id="evidence-147", collected_at=NOW.isoformat(),
                      used_percent=92, filesystem="/fs-lab", read_only=True)

    def analyst(self, request, observation):
        self.calls.append("analyst")
        return scoped(evidence_id="evidence-147", findings=["High lab utilization"])

    def critic(self, request, observation, analysis):
        self.calls.append("critic")
        return scoped(evidence_id="evidence-147", state="PASS")

    def policy(self, request, observation, analysis, critique):
        self.calls.append("policy")
        return scoped(evidence_id="evidence-147", state="PASS", decision="SIMULATE")

    def run(self, **overrides):
        callbacks = dict(stop_auto=False, claim_once=self.claim, observe=self.observe,
                         analyst=self.analyst, critic=self.critic, policy=self.policy,
                         now=lambda: NOW)
        callbacks.update(overrides)
        return execute(REQ, **callbacks)

    def assert_no_effect(self, result):
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertNotEqual(result["status"], "RESOLVED")

    def test_readonly_pipeline_and_duplicate_resume(self):
        first = self.run()
        self.assert_no_effect(first)
        self.assertEqual(first["status"], "NO_EFFECT")
        self.assertEqual(first["steps"], ["OBSERVE", "ANALYST", "CRITIC", "POLICY"])
        self.assertEqual(first["run_id"], REQ.run_id)
        self.assertEqual(first["ticket_id"], 147)
        before = list(self.calls)
        again = self.run()
        self.assert_no_effect(again)
        self.assertEqual(again["reason"], "DUPLICATE_RUN")
        self.assertEqual(self.calls, before + ["claim"])

    def test_insufficient_observation_stops_downstream(self):
        result = self.run(observe=lambda request: scoped(
            source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
            evidence_id="", collected_at=NOW.isoformat(),
            used_percent=92, filesystem="/fs-lab", read_only=True))
        self.assert_no_effect(result)
        self.assertEqual(result["reason"], "INSUFFICIENT_OBSERVATION")
        self.assertEqual(self.calls, ["claim"])

    def test_critic_refusal_skips_policy(self):
        def refuse(*args):
            self.calls.append("critic")
            return scoped(evidence_id="evidence-147", state="REFUSE")
        result = self.run(critic=refuse)
        self.assert_no_effect(result)
        self.assertEqual(result["reason"], "CRITIC_REFUSED")
        self.assertNotIn("policy", self.calls)

    def test_policy_execute_refused_even_if_pass(self):
        result = self.run(policy=lambda *args: scoped(
            evidence_id="evidence-147", state="PASS", decision="EXECUTE"))
        self.assert_no_effect(result)
        self.assertEqual(result["reason"], "POLICY_REFUSED")

    def test_unknown_transport_error_fails_closed(self):
        def timeout(*args):
            raise TimeoutError("upstream timeout")
        result = self.run(analyst=timeout)
        self.assert_no_effect(result)
        self.assertEqual(result["reason"], "SERVICE_UNAVAILABLE")
        self.assertEqual(result["steps"], ["OBSERVE"])

    def test_stop_auto_claims_nothing(self):
        result = self.run(stop_auto=True)
        self.assert_no_effect(result)
        self.assertEqual(result["reason"], "STOP_AUTO")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
