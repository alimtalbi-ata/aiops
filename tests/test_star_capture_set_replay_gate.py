"""Pure offline tests; real manifest gate import, synthetic mocked return values."""
import unittest
from pathlib import Path
from unittest.mock import patch

from demo.star_capture_set_replay_gate import verify_pinned_replay_captures

DIGEST = "a" * 64
CANONICAL = {"run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001", "events": {}}


def report(status="simulated"):
    return {"run_id": "RUN-ACME-001", "capture_set_sha256": DIGEST,
            "entries": [{"status": status} for _ in range(9)],
            "runtime_authenticated": False, "business_validated": False,
            "human_approval_authenticated": False, "live_action_authorized": False}


class ReplayGateTests(unittest.TestCase):
    def verify(self, pinned=DIGEST, fixture=False, result=None):
        with patch("demo.star_capture_set_replay_gate.verify_browser_manifests", return_value=result or report()) as gate:
            output = verify_pinned_replay_captures(Path("/unused"), CANONICAL, [], pinned,
                                                   allow_synthetic_fixture=fixture)
            gate.assert_called_once_with(Path("/unused"), CANONICAL, [], require_complete=True)
            return output

    def test_synthetic_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "synthetic fixture"):
            self.verify()

    def test_explicit_fixture_is_unreviewed(self):
        result = self.verify(fixture=True)
        self.assertEqual(result["provenance"], "ISOLATED_TEST_FIXTURE")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["business_validated"])

    def test_operator_provenance_remains_unreviewed(self):
        result = self.verify(result=report("integrity_checked"))
        self.assertEqual(result["provenance"], "OPERATOR_BROWSER_UNREVIEWED")
        self.assertFalse(result["human_approval_authenticated"])

    def test_wrong_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify(pinned="b" * 64, fixture=True)

    def test_malformed_pin_rejected_before_manifest_access(self):
        with patch("demo.star_capture_set_replay_gate.verify_browser_manifests") as gate:
            with self.assertRaisesRegex(ValueError, "pinned"):
                verify_pinned_replay_captures(Path("/unused"), CANONICAL, [], "bad")
            gate.assert_not_called()

    def test_mixed_provenance_rejected(self):
        mixed = report()
        mixed["entries"][-1]["status"] = "integrity_checked"
        with self.assertRaisesRegex(ValueError, "mixed"):
            self.verify(fixture=True, result=mixed)

    def test_malformed_entry_rejected(self):
        malformed = report()
        malformed["entries"][-1] = "simulated"
        with self.assertRaisesRegex(ValueError, "invalid replay checkpoint"):
            self.verify(fixture=True, result=malformed)

    def test_forged_runtime_attestation_rejected(self):
        forged = report()
        forged["runtime_authenticated"] = True
        with self.assertRaisesRegex(ValueError, "unexpected runtime"):
            self.verify(fixture=True, result=forged)

    def test_incomplete_set_rejected(self):
        short = report()
        short["entries"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.verify(fixture=True, result=short)

    def test_non_boolean_fixture_authorization_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixture authorization"):
            verify_pinned_replay_captures(Path("/unused"), CANONICAL, [], DIGEST,
                                          allow_synthetic_fixture=1)


if __name__ == "__main__":
    unittest.main()
