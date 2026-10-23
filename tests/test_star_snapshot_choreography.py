import unittest

from demo.star_snapshot_choreography import CUES, build_timeline, validate_capture

class SnapshotChoreographyTests(unittest.TestCase):
    def test_missing_is_never_a_real_capture(self):
        timeline = build_timeline({})
        self.assertEqual(len(timeline), len(CUES))
        self.assertTrue(all(not step["verified_real_capture"] for step in timeline))

    def test_synthetic_cannot_claim_real(self):
        with self.assertRaises(ValueError):
            validate_capture("detect", {
                "service": "grafana", "view": "alert_dashboard",
                "proof_state": "simulated", "claim_real": True,
            })

    def test_capture_requires_sha_and_provenance(self):
        record = {"service": "grafana", "view": "alert_dashboard",
                  "proof_state": "captured", "source_url": "http://localhost:3000/",
                  "captured_at": "2026-10-22T20:00:00+02:00",
                  "run_id": "DEMO-ONLY", "screenshot_path": "evidence/demo.png",
                  "sha256": "a" * 64}
        self.assertTrue(validate_capture("detect", record)["metadata_complete"])
        self.assertFalse(validate_capture("detect", record)["verified_real_capture"])
        with self.assertRaises(ValueError):
            validate_capture("detect", {**record, "sha256": "bad"})

    def test_wrong_application_page_refused(self):
        with self.assertRaises(ValueError):
            validate_capture("ticket", {"service": "grafana", "view": "incident_ticket"})

    def test_unknown_cue_refused(self):
        with self.assertRaises(ValueError):
            build_timeline({"undocumented": {}})

if __name__ == "__main__":
    unittest.main()
