"""Freshness gate: stale/future observations must never reach agents."""
import unittest
from datetime import datetime, timedelta, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

NOW = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "run")

class ObservationFreshnessTests(unittest.TestCase):
    def run_case(self, age_seconds):
        called = []
        observation = dict(tenant_id="tenant", actor_id="actor",
            incident_id="incident", run_id="run", ticket_id=147,
            evidence_id="evidence", source="fs-lab-bridge-readonly",
            commands=["df", "du", "ls"], read_only=True,
            filesystem="/fs-lab", used_percent=92,
            collected_at=(NOW - timedelta(seconds=age_seconds)).isoformat())
        def observe(_):
            called.append("observe")
            return observation
        def analyst(*_):
            called.append("analyst")
            return dict(tenant_id="tenant", incident_id="incident",
                        run_id="run", ticket_id=147, evidence_id="evidence",
                        findings=["lab disk pressure"])
        def critic(*_):
            called.append("critic")
            return dict(tenant_id="tenant", incident_id="incident",
                        run_id="run", ticket_id=147, evidence_id="evidence",
                        state="PASS")
        def policy(*_):
            called.append("policy")
            return dict(tenant_id="tenant", incident_id="incident",
                        run_id="run", ticket_id=147, evidence_id="evidence",
                        state="PASS", decision="SIMULATE")
        result = execute(REQ, stop_auto=False, claim_once=lambda _: True,
                         observe=observe, analyst=analyst, critic=critic,
                         policy=policy, now=lambda: NOW)
        return result, called

    def test_stale_measurement_short_circuits(self):
        result, called = self.run_case(301)
        self.assertEqual(result["reason"], "STALE_OBSERVATION")
        self.assertEqual(result["effect"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(called, ["observe"])

    def test_future_measurement_short_circuits(self):
        result, called = self.run_case(-31)
        self.assertEqual(result["reason"], "STALE_OBSERVATION")
        self.assertEqual(called, ["observe"])

    def test_recent_measurement_allows_policy_but_never_resolution(self):
        result, called = self.run_case(30)
        self.assertEqual(result["status"], "NO_EFFECT")
        self.assertFalse(result["resolved"])
        self.assertEqual(called, ["observe", "analyst", "critic", "policy"])

if __name__ == "__main__":
    unittest.main()
