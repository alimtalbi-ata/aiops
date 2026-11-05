"""Negative identity-binding tests for the selected FS Evidence record.

Pure synthetic contract tests: not proof of an Evidence service response.
"""
import unittest

from worker.fs_debian_bound_contract import decide_bound_fs_stage


class SelectedEvidenceRecordTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "tenant_id": "tenant-demo",
            "incident_id": "INC-FS",
            "run_id": "RUN-4FABD1786F107E51",
            "evidence_id": "EVD-D2069BA816126499",
        }
        self.evidence = {
            **self.expected,
            "verified": True,
            "synthetic": True,
        }
        self.policy = {
            **self.expected,
            "state": "PASS",
            "decision": "SIMULATE",
        }

    def decide(self, evidence=None, policy=None, stage="POLICY", expected=None):
        return decide_bound_fs_stage(
            scenario="FS-DEBIAN-SYNTHETIC", mode="DEMO", stage=stage,
            expected=self.expected if expected is None else expected,
            evidence=self.evidence if evidence is None else evidence,
            policy=self.policy if policy is None else policy,
        )

    def test_selected_record_allows_no_effect_only(self):
        result = self.decide()
        self.assertEqual(result.status, "NO_EFFECT")
        self.assertFalse(result.effect_allowed)
        self.assertFalse(result.resolve_allowed)

    def test_other_record_same_run_is_blocked(self):
        result = self.decide(evidence={**self.evidence, "evidence_id": "EVD-OTHER"})
        self.assertEqual((result.status, result.reason),
                         ("BLOCKED", "evidence_record_mismatch"))

    def test_missing_selected_record_is_blocked(self):
        result = self.decide(evidence={k: v for k, v in self.evidence.items()
                                       if k != "evidence_id"})
        self.assertEqual(result.status, "BLOCKED")

    def test_empty_expected_record_is_blocked(self):
        result = self.decide(expected={**self.expected, "evidence_id": ""})
        self.assertEqual(result.status, "BLOCKED")

    def test_other_record_blocked_before_analyst(self):
        result = self.decide(stage="OBSERVE",
                             evidence={**self.evidence, "evidence_id": "EVD-OTHER"})
        self.assertEqual(result.status, "BLOCKED")

    def test_policy_refusal_never_resolves(self):
        result = self.decide(policy={**self.policy, "decision": "DENY"})
        self.assertEqual(result.status, "BLOCKED")
        self.assertFalse(result.effect_allowed)
        self.assertFalse(result.resolve_allowed)


if __name__ == "__main__":
    unittest.main()
