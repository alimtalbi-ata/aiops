"""Offline, independent snapshot identity contract. No browser/network required."""
import unittest
from demo.star_capture_identity_guard import verify_snapshot_identity

EXPECTED = {"run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001",
            "event_ref": "EXEC-77"}


class SnapshotIdentityGuardTests(unittest.TestCase):
    def test_exact_identity_only_not_business_proof(self):
        result = verify_snapshot_identity(EXPECTED, dict(EXPECTED))
        self.assertTrue(result["identity_consistent"])
        for claim in ("runtime_authenticated", "business_validated",
                      "human_approval_authenticated", "live_action_authorized"):
            self.assertFalse(result[claim])

    def test_missing_observed_is_never_fabricated(self):
        for key in EXPECTED:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                verify_snapshot_identity(EXPECTED, {k: v for k, v in EXPECTED.items() if k != key})

    def test_missing_expected_is_refused(self):
        for key in EXPECTED:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                verify_snapshot_identity({k: v for k, v in EXPECTED.items() if k != key}, EXPECTED)

    def test_cross_run_and_cross_correlation_are_refused(self):
        for key in EXPECTED:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "contradiction"):
                verify_snapshot_identity(EXPECTED, {**EXPECTED, key: "OTHER-123"})

    def test_no_whitespace_trim_or_substring_acceptance(self):
        for key in EXPECTED:
            for value in (EXPECTED[key] + " ", EXPECTED[key][:-1], " " + EXPECTED[key]):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    verify_snapshot_identity(EXPECTED, {**EXPECTED, key: value})

    def test_wrong_types_and_control_characters_refused(self):
        for value in (None, 42, "", "../escape", "RUN\nID", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify_snapshot_identity(EXPECTED, {**EXPECTED, "run_id": value})


if __name__ == "__main__":
    unittest.main()
