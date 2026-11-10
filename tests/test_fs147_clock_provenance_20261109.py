"""Regression: Worker rejects unverifiable host clocks at all freshness boundaries."""
import unittest
from datetime import datetime, timedelta, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

class ClockProvenanceTests(unittest.TestCase):
    def test_invalid_clock_at_each_stage_prevents_success(self):
        start = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        valid = start + timedelta(minutes=1)
        for stage in range(4):
            for invalid in (None, "2026-11-09", start.replace(tzinfo=None)):
                with self.subTest(stage=stage, invalid=invalid):
                    clock = iter([valid] * stage + [invalid])
                    calls = []
                    def analyst(*args):
                        calls.append("analyst")
                        return dict(scope, evidence_id="evidence", findings=["high usage"])
                    def critic(*args):
                        calls.append("critic")
                        return dict(scope, evidence_id="evidence", state="PASS")
                    def policy(*args):
                        calls.append("policy")
                        return dict(scope, evidence_id="evidence", state="PASS",
                                    decision="SIMULATE")
                    result = execute(FS147Request("tenant", "actor", "incident", "run"),
                                     stop_auto=False, observe=lambda req: observation,
                                     analyst=analyst, critic=critic, policy=policy,
                                     claim_once=lambda key: True, now=lambda: next(clock))
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(result["reason"], "CLOCK_UNVERIFIED")
                    self.assertEqual(result["effect"], "NO_EFFECT")
                    self.assertFalse(result["resolved"])
                    self.assertEqual(calls, ["analyst", "critic", "policy"][:stage])

if __name__ == "__main__":
    unittest.main()
