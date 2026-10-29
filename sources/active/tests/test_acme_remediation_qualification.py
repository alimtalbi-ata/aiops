"""No-I/O, fail-closed snapshot consistency tests."""
import unittest
from copy import deepcopy
from app.shared.acme_demo_offline import demo_receipt
from app.shared.acme_remediation_qualification import qualify_receipt


def snapshots(receipt):
    core = {
        "run_id": receipt["run_id"], "scenario_id": receipt["scenario_id"],
        "mode": "DEMO", "synthetic": True,
    }
    evidence = [
        {"run_id": receipt["run_id"], "evidence_id": x,
         "synthetic": True, "source_qualified": True}
        for x in receipt["evidence_ids"]
    ]
    return core, evidence


class QualificationTests(unittest.TestCase):
    def test_consistent_snapshot_is_not_runtime_attestation(self):
        receipt = demo_receipt()
        result = qualify_receipt(receipt, *snapshots(receipt))
        self.assertEqual(result["qualification"], "SNAPSHOT_CONSISTENT_NOT_ATTESTED")
        self.assertTrue(result["core_snapshot_match"])
        self.assertTrue(result["evidence_snapshot_match"])
        self.assertFalse(result["core_run_verified"])
        self.assertFalse(result["evidence_verified"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertFalse(result["effect_applied"])

    def test_missing_snapshots_fail_closed(self):
        result = qualify_receipt(demo_receipt(), None, None)
        self.assertEqual(result["qualification"], "UNKNOWN")
        self.assertFalse(result["core_snapshot_match"])

    def test_wrong_run_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        core["run_id"] = "RUN-OTHER"
        result = qualify_receipt(receipt, core, evidence)
        self.assertEqual(result["qualification_reason"], "CORE_IDENTITY_MISMATCH")

    def test_live_mode_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        core["mode"] = "LIVE"
        result = qualify_receipt(receipt, core, evidence)
        self.assertEqual(result["qualification_reason"], "CORE_IDENTITY_MISMATCH")

    def test_wrong_scenario_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        core["scenario_id"] = "OTHER"
        self.assertEqual(qualify_receipt(receipt, core, evidence)["qualification"], "UNKNOWN")

    def test_missing_evidence_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        self.assertEqual(qualify_receipt(receipt, core, evidence[:1])["qualification_reason"],
                         "EVIDENCE_SET_MISMATCH")

    def test_cross_run_evidence_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        evidence[0]["run_id"] = "RUN-OTHER"
        self.assertEqual(qualify_receipt(receipt, core, evidence)["qualification_reason"],
                         "EVIDENCE_UNQUALIFIED")

    def test_unqualified_evidence_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        evidence[0]["source_qualified"] = False
        self.assertEqual(qualify_receipt(receipt, core, evidence)["qualification"], "UNKNOWN")

    def test_duplicate_evidence_fails(self):
        receipt = demo_receipt()
        core, evidence = snapshots(receipt)
        evidence[1] = deepcopy(evidence[0])
        self.assertEqual(qualify_receipt(receipt, core, evidence)["qualification_reason"],
                         "EVIDENCE_SET_MISMATCH")

    def test_forged_verified_input_fails(self):
        receipt = demo_receipt()
        receipt["core_run_verified"] = True
        result = qualify_receipt(receipt, *snapshots(receipt))
        self.assertEqual(result["qualification_reason"], "UNSAFE_INPUT_CLAIMS")
        self.assertFalse(result["core_run_verified"])

    def test_original_receipt_not_modified(self):
        receipt = demo_receipt()
        original = deepcopy(receipt)
        qualify_receipt(receipt, *snapshots(receipt))
        self.assertEqual(receipt, original)


if __name__ == "__main__":
    unittest.main()
