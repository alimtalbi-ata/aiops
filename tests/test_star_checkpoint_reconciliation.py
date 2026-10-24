import unittest
from demo.star_checkpoint_reconciliation import reconcile_checkpoints

SHA = "a" * 64

class CheckpointReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"run_id": "RUN-123", "correlation_id": "CORR-123", "events": {"san": "EVT-001", "payments": "EVT-002"}}
        self.captures = [
            {"cue": cue, "run_id": "RUN-123", "correlation_id": "CORR-123",
             "event_ref": event, "sha256": SHA, "provenance": "ISOLATED_TEST_FIXTURE",
             "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF", "runtime_page_authenticated": False,
             "business_outcome_verified": False, "human_approval_authenticated": False}
            for cue, event in self.expected["events"].items()
        ]

    def test_complete_unreviewed(self):
        result = reconcile_checkpoints(self.expected, self.captures)
        self.assertEqual(result["status"], "CAPTURES_UNREVIEWED")
        self.assertEqual(len(result["checkpoints"]), 2)

    def test_missing_checkpoint(self):
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures[:1])

    def test_duplicate_checkpoint(self):
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, [self.captures[0], self.captures[0]])

    def test_wrong_canonical_identity(self):
        self.captures[0]["run_id"] = "RUN-OTHER"
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures)

    def test_forged_attestation(self):
        self.captures[0]["runtime_page_authenticated"] = True
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures)

    def test_missing_attestation_is_not_false(self):
        del self.captures[0]["human_approval_authenticated"]
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures)

    def test_missing_independent_event_map(self):
        with self.assertRaises(ValueError):
            reconcile_checkpoints({**self.expected, "events": {}}, self.captures)

    def test_invalid_hash(self):
        self.captures[0]["sha256"] = "bad"
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures)

    def test_unreviewed_only(self):
        self.captures[0]["qualification"] = "PASS"
        with self.assertRaises(ValueError):
            reconcile_checkpoints(self.expected, self.captures)


if __name__ == "__main__":
    unittest.main()
