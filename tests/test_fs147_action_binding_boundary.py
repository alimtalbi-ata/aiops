"""Action-bound HITL artifacts must never enter the FS147 read-only pipeline."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

NOW = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
SCOPE = dict(tenant_id="t", actor_id="a", incident_id="i",
             run_id="r", ticket_id=147, evidence_id="e")


class ActionBindingBoundaryTests(unittest.TestCase):
    def exercise(self, stage, field, value):
        calls, claimed = [], set()

        def observe(_):
            calls.append("observe")
            out = dict(SCOPE, source="fs-lab-bridge-readonly",
                       commands=["df", "du", "ls"], filesystem="/fs-lab",
                       read_only=True, used_percent=42,
                       collected_at=NOW.isoformat())
            if stage == "observe":
                out[field] = value
            return out

        def analyst(*_):
            calls.append("analyst")
            out = dict(SCOPE, findings=["filesystem usage observed"])
            if stage == "analyst":
                out[field] = value
            return out

        def critic(*_):
            calls.append("critic")
            out = dict(SCOPE, state="PASS", validated=True,
                       missing_information=[])
            if stage == "critic":
                out[field] = value
            return out

        def policy(*_):
            calls.append("policy")
            out = dict(SCOPE, state="PASS", decision="SIMULATE",
                       effect="NO_EFFECT", dispatch_allowed=False)
            if stage == "policy":
                out[field] = value
            return out

        def claim_once(key):
            if key in claimed:
                return False
            claimed.add(key)
            return True

        args = dict(stop_auto=False, observe=observe, analyst=analyst,
                    critic=critic, policy=policy, claim_once=claim_once,
                    now=lambda: NOW)
        request = FS147Request("t", "a", "i", "r")
        first = execute(request, **args)
        replay = execute(request, **args)
        self.assertEqual(first["status"], "BLOCKED")
        self.assertEqual(first["effect"], "NO_EFFECT")
        self.assertFalse(first["resolved"])
        self.assertEqual(first["reason"], {
            "observe": "INSUFFICIENT_OBSERVATION",
            "analyst": "ANALYST_SIDE_EFFECT",
            "critic": "CRITIC_SIDE_EFFECT",
            "policy": "POLICY_REFUSED",
        }[stage])
        self.assertEqual(replay["reason"], "DUPLICATE_RUN")
        self.assertEqual(calls, ["observe", "analyst", "critic", "policy"][
            :{"observe": 1, "analyst": 2, "critic": 3, "policy": 4}[stage]])

    def test_action_binding_claims_fail_closed_at_every_boundary(self):
        for stage in ("observe", "analyst", "critic", "policy"):
            for field in ("approval_binding", "approval_token", "action_intent"):
                for value in (None, {}, "", {"action_id": "a-1"}):
                    with self.subTest(stage=stage, field=field, value=value):
                        self.exercise(stage, field, value)


if __name__ == "__main__":
    unittest.main()
