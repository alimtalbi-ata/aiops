"""FS147 blocked receipts retain scoped lineage without trusting rejected evidence."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

NOW = datetime(2026, 11, 10, 9, 20, tzinfo=timezone.utc)
REQ = FS147Request("tenant-a", "actor-a", "incident-a", "run-a")


class BlockedLineageTests(unittest.TestCase):
    def run_case(self, *, observation=None, analyst_error=None, replay=False):
        claimed = set()
        calls = []
        def claim(key):
            if key in claimed:
                return False
            claimed.add(key)
            return True
        def observe(_):
            calls.append("observe")
            return observation if observation is not None else dict(
                tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
                run_id="run-a", ticket_id=147, evidence_id="evidence-a",
                source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                filesystem="/fs-lab", read_only=True, used_percent=42,
                collected_at=NOW.isoformat())
        def analyst(*_):
            calls.append("analyst")
            if analyst_error:
                raise analyst_error
            return dict(tenant_id="tenant-a", actor_id="actor-a",
                        incident_id="incident-a", run_id="run-a", ticket_id=147,
                        evidence_id="evidence-a", findings=["observed"])
        def critic(*_):
            calls.append("critic")
            return dict(tenant_id="tenant-a", actor_id="actor-a",
                        incident_id="incident-a", run_id="run-a", ticket_id=147,
                        evidence_id="evidence-a", state="PASS")
        def policy(*_):
            calls.append("policy")
            return dict(tenant_id="tenant-a", actor_id="actor-a",
                        incident_id="incident-a", run_id="run-a", ticket_id=147,
                        evidence_id="evidence-a", state="PASS",
                        decision="SIMULATE", effect="NO_EFFECT")
        kwargs = dict(stop_auto=False, observe=observe, analyst=analyst,
                      critic=critic, policy=policy, claim_once=claim, now=lambda: NOW)
        first = execute(REQ, **kwargs)
        second = execute(REQ, **kwargs) if replay else None
        return first, second, calls

    def assert_scope(self, result):
        self.assertEqual(result["tenant_id"], "tenant-a")
        self.assertEqual(result["incident_id"], "incident-a")
        self.assertEqual(result["run_id"], "run-a")
        self.assertEqual(result["ticket_id"], 147)
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])

    def test_timeout_keeps_validated_evidence_and_replay_is_idempotent(self):
        first, replay, calls = self.run_case(
            analyst_error=TimeoutError("timeout"), replay=True)
        self.assert_scope(first)
        self.assertEqual(first["reason"], "UNKNOWN_TIMEOUT")
        self.assertEqual(first["evidence_id"], "evidence-a")
        self.assertEqual(first["steps"], ["OBSERVE"])
        self.assert_scope(replay)
        self.assertEqual(replay["reason"], "DUPLICATE_RUN")
        self.assertNotIn("evidence_id", replay)
        self.assertEqual(calls, ["observe", "analyst"])

    def test_rejected_bridge_evidence_is_not_echoed(self):
        observation = dict(tenant_id="tenant-a", actor_id="actor-a",
                           incident_id="incident-a", run_id="run-a",
                           ticket_id=147, evidence_id="forged",
                           source="untrusted", read_only=True)
        first, _, calls = self.run_case(observation=observation)
        self.assert_scope(first)
        self.assertEqual(first["reason"], "INSUFFICIENT_OBSERVATION")
        self.assertNotIn("evidence_id", first)
        self.assertEqual(calls, ["observe"])

    def test_critic_denial_preserves_evidence(self):
        first, _, calls = self.run_case()
        self.assertEqual(first["status"], "NO_EFFECT")
        self.assertEqual(first["evidence_id"], "evidence-a")
        self.assertEqual(calls, ["observe", "analyst", "critic", "policy"])


if __name__ == "__main__":
    unittest.main()
