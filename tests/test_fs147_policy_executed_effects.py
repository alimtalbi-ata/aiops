"""Policy SIMULATE must reject claimed executed actions and ticket transitions."""
import unittest
from datetime import datetime, timedelta, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class PolicyExecutionContradictionTests(unittest.TestCase):
    def run_case(self, extra):
        start = datetime(2026, 11, 9, 22, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        times = iter(start + timedelta(seconds=n) for n in (40, 41, 42, 43))
        return execute(
            FS147Request("tenant", "actor", "incident", "run"),
            stop_auto=False, observe=lambda _: observation,
            analyst=lambda *_: dict(scope, evidence_id="evidence",
                                    findings=["high usage"]),
            critic=lambda *_: dict(scope, evidence_id="evidence",
                                  state="PASS", validated=True,
                                  missing_information=[]),
            policy=lambda *_: dict(scope, evidence_id="evidence",
                                   state="PASS", decision="SIMULATE", **extra),
            claim_once=lambda _: True, now=lambda: next(times))

    def test_explicit_side_effects_refused(self):
        for metadata in (
            {"action_executed": True}, {"action_executed": None},
            {"action_executed": "false"}, {"remediation_executed": True},
            {"remediation_executed": None}, {"ticket_transition": "RESOLVED"},
            {"ticket_transition": ""}):
            with self.subTest(metadata=metadata):
                result = self.run_case(metadata)
                self.assertEqual(result["reason"], "POLICY_REFUSED")
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertFalse(result["resolved"])

    def test_explicit_no_effect_allowed(self):
        result = self.run_case(dict(action_executed=False, remediation_executed=False,
                                    ticket_transition=None))
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])


if __name__ == "__main__":
    unittest.main()
