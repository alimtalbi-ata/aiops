"""Fail closed when the wall clock rolls back between authenticated stages."""
import unittest
from datetime import datetime, timedelta, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class ClockRollbackTests(unittest.TestCase):
    def test_rollback_after_analyst_never_reaches_critic(self):
        start = datetime(2026, 11, 9, 19, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        calls = []

        def analyst(*args):
            calls.append("analyst")
            return dict(scope, evidence_id="evidence", findings=["high usage"])

        def critic(*args):
            calls.append("critic")
            return dict(scope, evidence_id="evidence", state="PASS")

        def policy(*args):
            calls.append("policy")
            return dict(scope, evidence_id="evidence", state="PASS", decision="SIMULATE")

        times = iter([start + timedelta(seconds=40), start + timedelta(seconds=39)])
        result = execute(FS147Request("tenant", "actor", "incident", "run"),
                         stop_auto=False, observe=lambda req: observation,
                         analyst=analyst, critic=critic, policy=policy,
                         claim_once=lambda key: True, now=lambda: next(times))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "CLOCK_UNVERIFIED")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(calls, ["analyst"])

    def test_stable_clock_does_not_reject_valid_read_only_run(self):
        start = datetime(2026, 11, 9, 19, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        times = iter([start + timedelta(seconds=i) for i in (40, 41, 42, 43)])
        result = execute(FS147Request("tenant", "actor", "incident", "run"),
                         stop_auto=False, observe=lambda req: observation,
                         analyst=lambda *args: dict(scope, evidence_id="evidence", findings=["high usage"]),
                         critic=lambda *args: dict(scope, evidence_id="evidence", state="PASS"),
                         policy=lambda *args: dict(scope, evidence_id="evidence", state="PASS", decision="SIMULATE"),
                         claim_once=lambda key: True, now=lambda: next(times))
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])


if __name__ == "__main__":
    unittest.main()
