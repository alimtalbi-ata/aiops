"""Analyst UNKNOWN/insufficient data must never be promoted to Critic/Policy."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class AnalystVerdictGateTests(unittest.TestCase):
    def setUp(self):
        self.scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                          run_id="run", ticket_id=147, evidence_id="ev-1")
        self.calls = []
        self.claims = set()

    def observe(self, *_):
        self.calls.append("observe")
        return dict(self.scope, source="fs-lab-bridge-readonly", commands=["df", "du", "ls"],
                    filesystem="/fs-lab", read_only=True, used_percent=51,
                    collected_at="2026-11-10T05:00:00+00:00")

    def analyst(self, *_):
        self.calls.append("analyst")
        return dict(self.scope, findings=["measured"])

    def critic(self, *_):
        self.calls.append("critic")
        return dict(self.scope, state="PASS", validated=True, missing_information=[])

    def policy(self, *_):
        self.calls.append("policy")
        return dict(self.scope, state="PASS", decision="SIMULATE", effect="NO_EFFECT",
                    dispatch_allowed=False)

    def claim(self, key):
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    def run_case(self, analyst=None):
        return execute(FS147Request("tenant", "actor", "incident", "run"),
                       stop_auto=False, claim_once=self.claim, observe=self.observe,
                       analyst=analyst or self.analyst, critic=self.critic,
                       policy=self.policy,
                       now=lambda: datetime(2026, 11, 10, 5, 0, tzinfo=timezone.utc))

    def test_explicit_unknown_or_invalid_verdict_blocks_before_critic(self):
        for field, value in (
            ("state", "UNKNOWN"), ("state", "REFUSED"), ("state", False),
            ("validated", False), ("validated", "true"),
            ("missing_information", ["unverified capacity"]),
            ("missing_information", None),
        ):
            with self.subTest(field=field, value=value):
                self.claims.clear()
                self.calls.clear()
                def adverse(*args, _field=field, _value=value):
                    return dict(self.analyst(*args), **{_field: _value})
                result = self.run_case(adverse)
                self.assertEqual((result["status"], result["reason"], result["effect"]),
                                 ("BLOCKED", "INSUFFICIENT_ANALYSIS", "NO_EFFECT"))
                self.assertEqual(self.calls, ["observe", "analyst"])
                # Re-delivery of same run must not invoke any external callback.
                again = self.run_case()
                self.assertEqual(again["reason"], "DUPLICATE_RUN")
                self.assertEqual(self.calls, ["observe", "analyst"])

    def test_explicit_valid_verdict_remains_readonly(self):
        for state in ("PASS", "COMPLETE"):
            self.claims.clear()
            self.calls.clear()
            def accepted(*args, _state=state):
                return dict(self.analyst(*args), state=_state, validated=True,
                            missing_information=[])
            result = self.run_case(accepted)
            self.assertEqual(result["status"], "NO_EFFECT")
            self.assertEqual(result["effect"], "NO_EFFECT")
            self.assertEqual(self.calls, ["observe", "analyst", "critic", "policy"])


if __name__ == "__main__":
    unittest.main()
