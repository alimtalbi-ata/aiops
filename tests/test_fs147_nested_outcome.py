"""Nested read-only outcome claims must not bypass stage-level gates."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute, _claims_side_effect

NOW = datetime(2026, 11, 10, 12, 19, tzinfo=timezone.utc)
REQ = FS147Request("tenant-a", "actor-a", "incident-a", "run-a")

def envelope(**extra):
    return dict(tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
                run_id="run-a", ticket_id=147, evidence_id="evidence-a", **extra)

class NestedOutcomeTests(unittest.TestCase):
    def test_nested_outcome_denials(self):
        for value in ({"metadata": {"resolved": True}},
                      {"metadata": {"resolved": None}},
                      {"metadata": {"ticket_transition": "RESOLVED"}},
                      {"audit": [{"effect": "LIVE"}]},
                      {"audit": [{"effect": None}]}):
            with self.subTest(value=value):
                self.assertTrue(_claims_side_effect(value))

    def test_safe_nested_outcomes(self):
        self.assertFalse(_claims_side_effect(
            {"metadata": {"resolved": False, "ticket_transition": None,
                          "effect": "NO_EFFECT"}}))

    def test_stage_refusal_and_idempotent_replay(self):
        for stage in ("observe", "analyst", "critic", "policy"):
            with self.subTest(stage=stage):
                calls, claimed = [], set()
                def claim(key):
                    if key in claimed:
                        return False
                    claimed.add(key)
                    return True
                def decorate(name, payload):
                    calls.append(name)
                    if name == stage:
                        payload["metadata"] = {"ticket_transition": "RESOLVED"}
                    return payload
                def observe(_):
                    return decorate("observe", envelope(
                        source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                        filesystem="/fs-lab", read_only=True, used_percent=42,
                        collected_at=NOW.isoformat()))
                def analyst(*_):
                    return decorate("analyst", envelope(findings=["observed"]))
                def critic(*_):
                    return decorate("critic", envelope(state="PASS"))
                def policy(*_):
                    return decorate("policy", envelope(
                        state="PASS", decision="SIMULATE", effect="NO_EFFECT"))
                kwargs = dict(stop_auto=False, observe=observe, analyst=analyst,
                              critic=critic, policy=policy, claim_once=claim,
                              now=lambda: NOW)
                first = execute(REQ, **kwargs)
                self.assertEqual(first["status"], "BLOCKED")
                self.assertEqual(first["effect"], "NO_EFFECT")
                self.assertFalse(first["resolved"])
                before = len(calls)
                replay = execute(REQ, **kwargs)
                self.assertEqual(replay["reason"], "DUPLICATE_RUN")
                self.assertEqual(len(calls), before)

if __name__ == "__main__":
    unittest.main()
