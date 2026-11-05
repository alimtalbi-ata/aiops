"""No host/Temporal/GLPI calls; contract-only tests."""
import unittest
from worker.fs_debian_stage_contract import decide_fs_stage

E = dict(verified=True, synthetic=True, tenant_id="T1",
         incident_id="I1", run_id="RUN-4FABD1786F107E51",
         evidence_id="EVD-D2069BA816126499")


class FSDemoContractTests(unittest.TestCase):
    def decide(self, stage="OBSERVE", **changes):
        args = dict(scenario="FS-DEBIAN-SYNTHETIC", mode="DEMO",
                    stage=stage, evidence=E)
        args.update(changes)
        return decide_fs_stage(**args)

    def test_sequence_never_enters_san_or_remediate(self):
        for stage, next_stage in (
            ("OBSERVE", "DGX_ANALYST"),
            ("DGX_ANALYST", "DGX_CRITIC"),
            ("DGX_CRITIC", "POLICY"),
        ):
            with self.subTest(stage=stage):
                d = self.decide(stage)
                self.assertEqual((d.status, d.next_stage), ("CONTINUE", next_stage))
                self.assertFalse(d.effect_allowed)
                self.assertFalse(d.resolve_allowed)

    def test_policy_refusal_is_blocked_not_resolved(self):
        for verdict in (None, {}, {"state": "BLOCKED", "decision": "REJECT"},
                        {"state": "PASS", "decision": "HUMAN_APPROVAL"}):
            with self.subTest(verdict=verdict):
                d = self.decide("POLICY", policy=verdict)
                self.assertEqual(d.status, "BLOCKED")
                self.assertIsNone(d.next_stage)
                self.assertFalse(d.resolve_allowed)

    def test_policy_pass_still_no_effect(self):
        d = self.decide("POLICY", policy={"state": "PASS", "decision": "SIMULATE"})
        self.assertEqual(d.status, "NO_EFFECT")
        self.assertFalse(d.effect_allowed)
        self.assertFalse(d.resolve_allowed)

    def test_missing_unverified_or_wrong_evidence_blocks(self):
        for evidence in (None, {}, {**E, "verified": False},
                         {**E, "synthetic": False}, {**E, "run_id": ""}):
            with self.subTest(evidence=evidence):
                self.assertEqual(self.decide(evidence=evidence).status, "BLOCKED")

    def test_stop_auto_blocks(self):
        self.assertEqual(self.decide(stop_auto=True).status, "BLOCKED")

    def test_other_demos_not_intercepted(self):
        d = self.decide(scenario="ACME-SAN")
        self.assertEqual(d.status, "NOT_APPLICABLE")

    def test_no_live_or_unknown_stage(self):
        self.assertEqual(self.decide(mode="LIVE").status, "NOT_APPLICABLE")
        self.assertEqual(self.decide(stage="REMEDIATE").status, "BLOCKED")
        self.assertEqual(self.decide(stage="VERIFY").status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
