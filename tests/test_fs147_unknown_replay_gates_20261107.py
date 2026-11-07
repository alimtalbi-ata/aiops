"""FS147 negative contract gates; injected callbacks only, never host execution."""
import unittest
from datetime import datetime, timezone, timedelta
from worker.fs147_readonly_pipeline import FS147Request, execute

NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "worker", "incident-147", "run-147")

def scope(**extra):
    return dict(tenant_id=REQ.tenant_id, actor_id=REQ.actor_id,
                incident_id=REQ.incident_id, run_id=REQ.run_id,
                ticket_id=147, **extra)

class FailClosedReplayTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.claims = set()

    def claim(self, key):
        self.events.append("claim")
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    def observe(self, request):
        self.events.append("bridge")
        return scope(source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                     commands=["df", "du", "ls"], read_only=True,
                     evidence_id="ev-147", collected_at=NOW.isoformat(),
                     used_percent=92)

    def analyst(self, request, observation):
        self.events.append("analyst")
        return scope(evidence_id="ev-147", findings=["lab utilization high"])

    def critic(self, request, observation, analysis):
        self.events.append("critic")
        return scope(evidence_id="ev-147", state="PASS")

    def policy(self, request, observation, analysis, critique):
        self.events.append("policy")
        return scope(evidence_id="ev-147", state="PASS", decision="SIMULATE")

    def run_pipeline(self, **overrides):
        args = dict(stop_auto=False, claim_once=self.claim, observe=self.observe,
                    analyst=self.analyst, critic=self.critic, policy=self.policy,
                    now=lambda: NOW)
        args.update(overrides)
        return execute(REQ, **args)

    def assert_blocked(self, response, reason):
        self.assertEqual(response["status"], "BLOCKED")
        self.assertEqual(response["reason"], reason)
        self.assertEqual(response["effect"], "NO_EFFECT")
        self.assertIs(response["resolved"], False)

    def test_timeout_then_replay_never_calls_bridge_twice(self):
        def timeout(*args):
            self.events.append("analyst-timeout")
            raise TimeoutError("injected timeout")
        first = self.run_pipeline(analyst=timeout)
        self.assert_blocked(first, "SERVICE_UNAVAILABLE")
        self.assertEqual(self.events, ["claim", "bridge", "analyst-timeout"])
        second = self.run_pipeline()
        self.assert_blocked(second, "DUPLICATE_RUN")
        self.assertEqual(self.events, ["claim", "bridge", "analyst-timeout", "claim"])

    def test_unknown_critic_never_calls_policy(self):
        def unknown(*args):
            self.events.append("critic-unknown")
            return scope(evidence_id="ev-147", state="UNKNOWN")
        result = self.run_pipeline(critic=unknown)
        self.assert_blocked(result, "CRITIC_REFUSED")
        self.assertNotIn("policy", self.events)

    def test_unknown_policy_is_not_a_success(self):
        result = self.run_pipeline(policy=lambda *args: scope(
            evidence_id="ev-147", state="UNKNOWN", decision="SIMULATE"))
        self.assert_blocked(result, "POLICY_REFUSED")

    def test_future_observation_outside_skew_rejected(self):
        def future(request):
            observation = self.observe(request)
            observation["collected_at"] = (NOW + timedelta(minutes=2)).isoformat()
            return observation
        result = self.run_pipeline(observe=future)
        self.assert_blocked(result, "STALE_OBSERVATION")
        self.assertEqual(self.events, ["claim", "bridge"])

    def test_claim_unavailable_never_observes(self):
        def unavailable(key):
            self.events.append("claim-unavailable")
            raise ConnectionError("injected Core failure")
        result = self.run_pipeline(claim_once=unavailable)
        self.assert_blocked(result, "IDEMPOTENCY_UNAVAILABLE")
        self.assertEqual(self.events, ["claim-unavailable"])

if __name__ == "__main__":
    unittest.main()
