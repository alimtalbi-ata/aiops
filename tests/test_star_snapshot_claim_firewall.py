"""Adversarial STAR snapshot metadata trust-boundary tests (synthetic only)."""
import unittest

from demo.star_snapshot_choreography import build_timeline, validate_capture


class SnapshotAttestationFirewallTests(unittest.TestCase):
    def capture(self):
        return {
            "service": "grafana", "view": "alert_dashboard",
            "proof_state": "captured",
            "source_url": "http://localhost:3000/d/acme-star",
            "captured_at": "2026-10-23T09:00:00+02:00",
            "run_id": "RUN-STAR-123", "screenshot_path": "evidence/fixture.png",
            "sha256": "a" * 64,
        }

    def test_no_captured_metadata_can_claim_runtime_business_hitl_or_live(self):
        for key in ("claim_real", "verified_real_capture", "runtime_authenticated",
                    "business_validated", "human_approval_authenticated",
                    "remediation_executed", "release_promotable",
                    "live_action_authorized"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "attestation"):
                validate_capture("detect", {**self.capture(), key: True})

    def test_nonboolean_claims_are_rejected(self):
        for value in (1, 0, "true", "yes", [], {}):
            with self.subTest(value=repr(value)), self.assertRaisesRegex(ValueError, "attestation"):
                validate_capture("detect", {**self.capture(), "runtime_authenticated": value})

    def test_missing_and_synthetic_cannot_assert_hitl(self):
        for state in ("missing", "simulated"):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "attestation"):
                validate_capture("detect", {
                    "service": "grafana", "view": "alert_dashboard",
                    "proof_state": state, "human_approval_authenticated": True,
                })

    def test_metadata_is_never_an_authenticated_runtime(self):
        record = {**self.capture(), "runtime_authenticated": False,
                  "business_validated": False, "claim_real": False}
        result = validate_capture("detect", record)
        self.assertTrue(result["metadata_complete"])
        for key in ("verified_real_capture", "business_validated",
                    "human_approval_authenticated", "live_action_authorized"):
            self.assertIs(result[key], False)

    def test_timeline_rejects_release_promotion_claim(self):
        with self.assertRaisesRegex(ValueError, "attestation"):
            build_timeline({"detect": {**self.capture(), "release_promotable": True}})

    def test_missing_timeline_is_not_business_qualified(self):
        for entry in build_timeline({}):
            self.assertIs(entry["business_validated"], False)
            self.assertIs(entry["live_action_authorized"], False)


if __name__ == "__main__":
    unittest.main()
