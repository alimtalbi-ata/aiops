"""FS147 must not treat approval/dispatch claims as harmless read-only metadata."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

SCOPE = dict(tenant_id="t", actor_id="a", incident_id="i", run_id="r",
             ticket_id=147, evidence_id="e")
NOW = datetime(2026, 11, 10, 7, 0, tzinfo=timezone.utc)
CLAIMS = ("approval_granted", "approval_consumed", "hitl_approved",
          "action_dispatched", "ticket_updated")


class HitlClaimsTests(unittest.TestCase):
    def run_case(self, stage, field, value):
        calls = []
        def observe(_):
            calls.append("observe")
            result = dict(SCOPE, source="fs-lab-bridge-readonly",
                          commands=["df", "du", "ls"], filesystem="/fs-lab",
                          read_only=True, used_percent=42,
                          collected_at=NOW.isoformat())
            if stage == "observe":
                result[field] = value
            return result

        def analyst(*_):
            calls.append("analyst")
            result = dict(SCOPE, findings=["read-only observation"])
            if stage == "analyst":
                result[field] = value
            return result

        def critic(*_):
            calls.append("critic")
            result = dict(SCOPE, state="PASS", validated=True,
                          missing_information=[])
            if stage == "critic":
                result[field] = value
            return result

        def policy(*_):
            calls.append("policy")
            result = dict(SCOPE, state="PASS", decision="SIMULATE",
                          effect="NO_EFFECT", dispatch_allowed=False)
            if stage == "policy":
                result[field] = value
            return result

        claims = set()
        def claim_once(key):
            if key in claims:
                return False
            claims.add(key)
            return True

        args = dict(stop_auto=False, observe=observe, analyst=analyst,
                    critic=critic, policy=policy, claim_once=claim_once,
                    now=lambda: NOW)
        request = FS147Request("t", "a", "i", "r")
        first = execute(request, **args)
        replay = execute(request, **args)
        self.assertEqual(first["effect"], "NO_EFFECT")
        self.assertFalse(first["resolved"])
        self.assertEqual(replay["reason"], "DUPLICATE_RUN")
        self.assertEqual(calls.count("observe"), 1)
        if value is False:
            self.assertEqual(first["status"], "NO_EFFECT")
            self.assertEqual(calls, ["observe", "analyst", "critic", "policy"])
        else:
            self.assertEqual(first["status"], "BLOCKED")
            self.assertEqual(first["reason"], {
                "observe": "INSUFFICIENT_OBSERVATION",
                "analyst": "ANALYST_SIDE_EFFECT",
                "critic": "CRITIC_SIDE_EFFECT",
                "policy": "POLICY_REFUSED",
            }[stage])
            self.assertEqual(calls, ["observe", "analyst", "critic", "policy"][
                :{"observe": 1, "analyst": 2, "critic": 3, "policy": 4}[stage]])

    def test_all_stages_reject_positive_or_ambiguous_hitl_claims(self):
        for stage in ("observe", "analyst", "critic", "policy"):
            for field in CLAIMS:
                for value in (True, None, "false", 1):
                    with self.subTest(stage=stage, field=field, value=value):
                        self.run_case(stage, field, value)

    def test_explicit_false_is_compatible(self):
        for stage in ("observe", "analyst", "critic", "policy"):
            for field in CLAIMS:
                with self.subTest(stage=stage, field=field):
                    self.run_case(stage, field, False)


if __name__ == "__main__":
    unittest.main()
