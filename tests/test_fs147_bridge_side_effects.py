"""Reject contradictory side effects in an otherwise read-only bridge observation."""
import unittest
from datetime import datetime, timedelta, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class BridgeSideEffectTests(unittest.TestCase):
    def run_case(self, extra):
        start = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)
        scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                     run_id="run", ticket_id=147)
        observation = dict(scope, source="fs-lab-bridge-readonly",
                           commands=["df", "du", "ls"], evidence_id="evidence",
                           collected_at=start.isoformat(), used_percent=90,
                           filesystem="/fs-lab", read_only=True, **extra)
        calls = []
        times = iter(start + timedelta(seconds=n) for n in (40, 41, 42, 43))
        def analyst(*args):
            calls.append("analyst")
            return dict(scope, evidence_id="evidence", findings=["high usage"])
        def critic(*args):
            calls.append("critic")
            return dict(scope, evidence_id="evidence", state="PASS",
                        validated=True, missing_information=[])
        def policy(*args):
            calls.append("policy")
            return dict(scope, evidence_id="evidence", state="PASS",
                        decision="SIMULATE", effect="NO_EFFECT")
        result = execute(FS147Request("tenant", "actor", "incident", "run"),
                         stop_auto=False, observe=lambda _: observation,
                         analyst=analyst, critic=critic, policy=policy,
                         claim_once=lambda _: True, now=lambda: next(times))
        return result, calls

    def test_mutation_claims_block_before_intelligence(self):
        for extra in ({"action_executed": True}, {"action_executed": None},
                      {"action_executed": "false"}, {"mutation_performed": True},
                      {"mutation_performed": None}, {"ticket_transition": "RESOLVED"},
                      {"ticket_transition": ""}):
            with self.subTest(extra=extra):
                result, calls = self.run_case(extra)
                self.assertEqual(result["reason"], "INSUFFICIENT_OBSERVATION")
                self.assertEqual(result["effect"], "NO_EFFECT")
                self.assertFalse(result["resolved"])
                self.assertEqual(calls, [])

    def test_explicit_no_effect_provenance_passes(self):
        result, calls = self.run_case(dict(action_executed=False,
                                           mutation_performed=False,
                                           ticket_transition=None))
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertEqual(calls, ["analyst", "critic", "policy"])


if __name__ == "__main__":
    unittest.main()
