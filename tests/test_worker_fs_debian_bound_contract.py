"""Contract tests only; no fabricated service calls or HITL."""
import unittest
from worker.fs_debian_bound_contract import decide_bound_fs_stage

EXPECTED = {"tenant_id": "T1", "incident_id": "INC-DEMO-FS-001",
            "run_id": "RUN-4FABD1786F107E51"}
EVIDENCE = {**EXPECTED, "evidence_id": "EVD-D2069BA816126499",
            "verified": True, "synthetic": True}
POLICY = {**EXPECTED, "state": "PASS", "decision": "SIMULATE"}


class BoundContractTests(unittest.TestCase):
    def decide(self, stage="POLICY", **overrides):
        args = dict(scenario="FS-DEBIAN-SYNTHETIC", mode="DEMO",
                    stage=stage, expected=EXPECTED, evidence=EVIDENCE,
                    policy=POLICY)
        args.update(overrides)
        return decide_bound_fs_stage(**args)

    def test_valid_workflow_no_effect(self):
        for stage, next_stage in (("OBSERVE", "DGX_ANALYST"),
                                  ("DGX_ANALYST", "DGX_CRITIC"),
                                  ("DGX_CRITIC", "POLICY")):
            with self.subTest(stage=stage):
                d = self.decide(stage)
                self.assertEqual((d.status, d.next_stage), ("CONTINUE", next_stage))
                self.assertFalse(d.effect_allowed)
        d = self.decide()
        self.assertEqual(d.status, "NO_EFFECT")
        self.assertFalse(d.resolve_allowed)

    def test_identity_mismatches_block(self):
        for key in ("tenant_id", "incident_id", "run_id"):
            with self.subTest(key=key):
                self.assertEqual(self.decide(evidence={**EVIDENCE, key: "other"}).status, "BLOCKED")
                self.assertEqual(self.decide(policy={**POLICY, key: "other"}).status, "BLOCKED")

    def test_missing_expected_or_policy_identity_blocks(self):
        self.assertEqual(self.decide(expected={}).status, "BLOCKED")
        self.assertEqual(self.decide(policy={"state": "PASS", "decision": "SIMULATE"}).status, "BLOCKED")

    def test_refusal_and_stop_auto_block(self):
        self.assertEqual(self.decide(policy={**POLICY, "decision": "REJECT"}).status, "BLOCKED")
        self.assertEqual(self.decide(stop_auto=True).status, "BLOCKED")

    def test_policy_allow_is_not_synthetic_authorization(self):
        for decision in ("ALLOW", "REMEDIATE", "VERIFY", None):
            with self.subTest(decision=decision):
                result = self.decide(policy={**POLICY, "decision": decision})
                self.assertEqual(result.status, "BLOCKED")
                self.assertIsNone(result.next_stage)
                self.assertFalse(result.effect_allowed)
                self.assertFalse(result.resolve_allowed)

    def test_only_explicit_simulate_finishes_without_effect(self):
        result = self.decide(policy={**POLICY, "decision": "SIMULATE"})
        self.assertEqual((result.status, result.next_stage), ("NO_EFFECT", None))
        self.assertFalse(result.effect_allowed)
        self.assertFalse(result.resolve_allowed)

    def test_other_demo_untouched(self):
        self.assertEqual(self.decide(scenario="SAN-DEMO").status, "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
