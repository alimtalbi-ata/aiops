"""Contract tests with explicit fake adapters; never claimed as host E2E."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

R = FS147Request("tenant", "actor", "incident", "run")


def scoped(**kwargs):
    return dict(tenant_id="tenant", incident_id="incident", run_id="run",
                ticket_id=147, evidence_id="evidence", **kwargs)


def observation(_):
    return scoped(source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                  read_only=True, used_percent=92, filesystem="/fs-lab",
                  collected_at=datetime.now(timezone.utc).isoformat())


def analyst(_, obs):
    return scoped(findings=["read-only saturation measurement"])


def critic(_, obs, analysis):
    return scoped(state="PASS")


def policy(_, obs, analysis, critique):
    return scoped(state="PASS", decision="SIMULATE")


class FS147Tests(unittest.TestCase):
    def run_pipeline(self, **overrides):
        calls = {"claims": set()}
        def claim(key):
            if key in calls["claims"]:
                return False
            calls["claims"].add(key)
            return True
        args = dict(stop_auto=False, observe=observation, analyst=analyst,
                    critic=critic, policy=policy, claim_once=claim)
        args.update(overrides)
        return execute(R, **args)

    def test_diagnostic_no_effect(self):
        result = self.run_pipeline()
        self.assertEqual(result["steps"], ["OBSERVE", "ANALYST", "CRITIC", "POLICY"])
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])

    def test_duplicate_durable_claim(self):
        keys = set()
        def claim(key):
            if key in keys:
                return False
            keys.add(key)
            return True
        args = dict(stop_auto=False, observe=observation, analyst=analyst,
                    critic=critic, policy=policy, claim_once=claim)
        self.assertEqual(execute(R, **args)["status"], "NO_EFFECT")
        self.assertEqual(execute(R, **args)["reason"], "DUPLICATE_RUN")

    def test_missing_measurement(self):
        self.assertEqual(self.run_pipeline(observe=lambda _: scoped(
            source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
            read_only=True, collected_at="now"))["reason"], "INSUFFICIENT_OBSERVATION")

    def test_nonfinite_or_boolean_measurements_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, False):
            with self.subTest(value=value):
                self.assertEqual(self.run_pipeline(
                    observe=lambda _, v=value: dict(observation(R), used_percent=v)
                )["reason"], "INSUFFICIENT_OBSERVATION")

    def test_wrong_filesystem_rejected(self):
        self.assertEqual(self.run_pipeline(
            observe=lambda _: dict(observation(R), filesystem="/")
        )["reason"], "INSUFFICIENT_OBSERVATION")

    def test_blank_evidence_id_rejected(self):
        self.assertEqual(self.run_pipeline(
            observe=lambda _: dict(observation(R), evidence_id="   ")
        )["reason"], "INSUFFICIENT_OBSERVATION")

    def test_policy_refusal(self):
        self.assertEqual(self.run_pipeline(policy=lambda *args: scoped(
            state="PASS", decision="DENY"))["reason"], "POLICY_REFUSED")

    def test_critic_refusal(self):
        self.assertEqual(self.run_pipeline(critic=lambda *args: scoped(
            state="BLOCKED"))["reason"], "CRITIC_REFUSED")

    def test_stop_auto(self):
        self.assertEqual(self.run_pipeline(stop_auto=True)["reason"], "STOP_AUTO")

    def test_wrong_ticket(self):
        self.assertEqual(execute(replace(R, ticket_id=146), stop_auto=False,
            observe=observation, analyst=analyst, critic=critic, policy=policy,
            claim_once=lambda _: True)["reason"], "INVALID_SCOPE")

    def test_cross_run_evidence(self):
        self.assertEqual(self.run_pipeline(observe=lambda _: dict(
            observation(R), run_id="other"))["reason"], "OBSERVATION_SCOPE")

    def test_bridge_unavailable(self):
        def offline(_):
            raise ConnectionError("offline")
        self.assertEqual(self.run_pipeline(observe=offline)["reason"], "SERVICE_UNAVAILABLE")

    def test_no_san_dependency(self):
        self.assertNotIn("SAN", repr(self.run_pipeline()))


if __name__ == "__main__":
    unittest.main()
