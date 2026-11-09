"""FS147 Critic explicit validation metadata must fail closed before Policy."""
import unittest
from datetime import datetime, timezone, timedelta
from worker.fs147_readonly_pipeline import FS147Request, execute


class CriticMetadataTests(unittest.TestCase):
    def test_critic_metadata_denials_do_not_reach_policy(self):
        start = datetime(2026, 11, 9, 21, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        for extra in ({"validated": False}, {"validated": "true"},
                      {"validated": None}, {"missing_information": ["unknown"]},
                      {"missing_information": "unknown"},
                      {"missing_information": None}):
            with self.subTest(extra=extra):
                calls = []
                times = iter([start + timedelta(seconds=i) for i in (40, 41, 42, 43)])
                result = execute(
                    FS147Request("tenant", "actor", "incident", "run"),
                    stop_auto=False, observe=lambda req: observation,
                    analyst=lambda *args: dict(scope, evidence_id="evidence",
                                               findings=["high usage"]),
                    critic=lambda *args: dict(scope, evidence_id="evidence",
                                              state="PASS", **extra),
                    policy=lambda *args: calls.append("policy"),
                    claim_once=lambda key: True, now=lambda: next(times))
                self.assertEqual(result["reason"], "CRITIC_REFUSED")
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertFalse(result["resolved"])
                self.assertEqual(calls, [])

    def test_explicit_validated_true_and_no_gaps_remains_readonly(self):
        start = datetime(2026, 11, 9, 21, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True)
        times = iter([start + timedelta(seconds=i) for i in (40, 41, 42, 43)])
        result = execute(
            FS147Request("tenant", "actor", "incident", "run"),
            stop_auto=False, observe=lambda req: observation,
            analyst=lambda *args: dict(scope, evidence_id="evidence",
                                       findings=["high usage"]),
            critic=lambda *args: dict(scope, evidence_id="evidence", state="PASS",
                                      validated=True, missing_information=[]),
            policy=lambda *args: dict(scope, evidence_id="evidence",
                                      state="PASS", decision="SIMULATE"),
            claim_once=lambda key: True, now=lambda: next(times))
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])


if __name__ == "__main__":
    unittest.main()
