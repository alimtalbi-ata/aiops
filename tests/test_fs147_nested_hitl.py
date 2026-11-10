"""Nested HITL claims must not bypass read-only FS147 stage validation."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute, _claims_side_effect

NOW = datetime(2026, 11, 10, 11, 20, tzinfo=timezone.utc)
REQ = FS147Request("tenant-a", "actor-a", "incident-a", "run-a")


def envelope(**extra):
    return dict(tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
                run_id="run-a", ticket_id=147, evidence_id="evidence-a", **extra)


class NestedHITLTests(unittest.TestCase):
    def test_nested_artifacts_and_claims_fail_closed(self):
        for artifact in ({"metadata": {"approval_binding": None}},
                         {"details": [{"action_intent": {}}]},
                         {"audit": {"approval_granted": True}},
                         {"metadata": {"action_dispatched": "false"}},
                         {"metadata": {"ticket_updated": 0}}):
            with self.subTest(artifact=artifact):
                self.assertTrue(_claims_side_effect(artifact))

    def test_explicit_false_nested_flags_are_safe(self):
        self.assertFalse(_claims_side_effect(
            {"metadata": {"approval_granted": False,
                          "action_dispatched": False,
                          "ticket_updated": False}}))

    def test_cycle_and_unbounded_depth_fail_closed(self):
        cycle = {}
        cycle["self"] = cycle
        self.assertTrue(_claims_side_effect(cycle))
        nested = {}
        for _ in range(20):
            nested = {"next": nested}
        self.assertTrue(_claims_side_effect(nested))

    def test_each_stage_refuses_nested_action_and_replay_does_not_call_adapters(self):
        for contaminated in ("observe", "analyst", "critic", "policy"):
            with self.subTest(stage=contaminated):
                calls, claims = [], set()
                def claim(key):
                    if key in claims:
                        return False
                    claims.add(key)
                    return True
                def add(stage, data):
                    calls.append(stage)
                    if stage == contaminated:
                        data["metadata"] = {"approval_token": None}
                    return data
                def observe(_):
                    return add("observe", envelope(
                        source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                        filesystem="/fs-lab", read_only=True, used_percent=42,
                        collected_at=NOW.isoformat()))
                def analyst(*_):
                    return add("analyst", envelope(findings=["observed"]))
                def critic(*_):
                    return add("critic", envelope(state="PASS"))
                def policy(*_):
                    return add("policy", envelope(state="PASS", decision="SIMULATE",
                                                  effect="NO_EFFECT"))
                kwargs = dict(stop_auto=False, observe=observe, analyst=analyst,
                              critic=critic, policy=policy, claim_once=claim,
                              now=lambda: NOW)
                first = execute(REQ, **kwargs)
                self.assertEqual(first["status"], "BLOCKED")
                self.assertEqual(first["effect"], "NO_EFFECT")
                self.assertEqual(first["run_id"], REQ.run_id)
                count = len(calls)
                second = execute(REQ, **kwargs)
                self.assertEqual(second["reason"], "DUPLICATE_RUN")
                self.assertEqual(len(calls), count)
                self.assertFalse(first["resolved"])


if __name__ == "__main__":
    unittest.main()
