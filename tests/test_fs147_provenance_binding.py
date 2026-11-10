"""Reject remote-stage evidence provenance substitution without side effects."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute


class ProvenanceBindingTests(unittest.TestCase):
    def setUp(self):
        self.request = FS147Request("tenant", "actor", "incident", "run")
        self.calls = []
        self.scope = dict(tenant_id="tenant", actor_id="actor",
                          incident_id="incident", run_id="run",
                          ticket_id=147, evidence_id="ev-1")
        self.observation = dict(self.scope, source="fs-lab-bridge-readonly",
                                commands=["df", "du", "ls"], filesystem="/fs-lab",
                                read_only=True, used_percent=51,
                                collected_at="2026-11-10T04:00:00+00:00")

    def observe(self, *_):
        self.calls.append("observe")
        return dict(self.observation)

    def analyst(self, *_):
        self.calls.append("analyst")
        return dict(self.scope, findings=["filesystem measured"])

    def critic(self, *_):
        self.calls.append("critic")
        return dict(self.scope, state="PASS", validated=True, missing_information=[])

    def policy(self, *_):
        self.calls.append("policy")
        return dict(self.scope, state="PASS", decision="SIMULATE",
                    effect="NO_EFFECT", dispatch_allowed=False)

    def execute_case(self, **overrides):
        callbacks = dict(observe=self.observe, analyst=self.analyst,
                         critic=self.critic, policy=self.policy)
        callbacks.update(overrides)
        return execute(self.request, stop_auto=False, claim_once=lambda _: True,
                       now=lambda: datetime(2026, 11, 10, 4, 0, tzinfo=timezone.utc),
                       **callbacks)

    def test_each_stage_rejects_echoed_provenance_substitution(self):
        for stage, reason, expected_calls in (
            ("analyst", "ANALYST_PROVENANCE", ["observe", "analyst"]),
            ("critic", "CRITIC_PROVENANCE", ["observe", "analyst", "critic"]),
            ("policy", "POLICY_PROVENANCE", ["observe", "analyst", "critic", "policy"]),
        ):
            for field, invalid in (
                ("source", "forged-bridge"),
                ("collected_at", "2026-11-10T04:01:00+00:00"),
                ("filesystem", "/other"),
                ("commands", ["df", "rm"]),
                ("read_only", False),
                ("used_percent", float("nan")),
            ):
                with self.subTest(stage=stage, field=field):
                    self.calls = []
                    original = getattr(self, stage)
                    def changed(*args, _original=original, _field=field, _invalid=invalid):
                        return dict(_original(*args), **{_field: _invalid})
                    result = self.execute_case(**{stage: changed})
                    self.assertEqual((result["status"], result["reason"], result["effect"]),
                                     ("BLOCKED", reason, "NO_EFFECT"))
                    self.assertEqual(self.calls, expected_calls)

    def test_consistent_echo_is_accepted_without_dispatch(self):
        for stage in ("analyst", "critic", "policy"):
            self.calls = []
            original = getattr(self, stage)
            def echoed(*args, _original=original):
                return dict(_original(*args),
                            **{key: self.observation[key] for key in (
                                "source", "collected_at", "filesystem",
                                "commands", "read_only", "used_percent")})
            result = self.execute_case(**{stage: echoed})
            self.assertEqual(result["status"], "NO_EFFECT")
            self.assertEqual(result["effect"], "NO_EFFECT")
            self.assertEqual(self.calls, ["observe", "analyst", "critic", "policy"])

    def test_no_provenance_echo_is_backward_compatible(self):
        result = self.execute_case()
        self.assertEqual(result["status"], "NO_EFFECT")


if __name__ == "__main__":
    unittest.main()
