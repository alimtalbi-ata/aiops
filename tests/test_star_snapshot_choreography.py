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


    def _capture(self, **changes):
        record = {"service": "grafana", "view": "alert_dashboard",
                  "proof_state": "captured", "source_url": "http://localhost:3000/d/acme-star",
                  "captured_at": "2026-10-22T20:00:00+02:00",
                  "run_id": "RUN-ACME-123", "screenshot_path": "evidence/acme.png",
                  "sha256": "a" * 64}
        record.update(changes)
        return record

    def test_metadata_rejects_traversal_and_encoded_paths(self):
        for path in ("evidence/../outside.png", "evidence/./x.png", "evidence//x.png",
                     "evidence/%2e%2e/x.png", "evidence\\..\\x.png", "/tmp/x.png",
                     "evidence/x.txt"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "evidence"):
                validate_capture("detect", self._capture(screenshot_path=path))

    def test_metadata_rejects_credential_and_token_urls(self):
        for url in ("http://user:pass@localhost:3000/d/acme-star",
                    "http://localhost:3000/d/acme-star?token=redacted",
                    "http://localhost:3000/d/acme-star#fragment",
                    "http://localhost:3000/d/acme-star?id=1&id=2"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "unsafe"):
                validate_capture("detect", self._capture(source_url=url))

    def test_metadata_rejects_unsafe_identity_and_naive_time(self):
        for run in ("RUN OTHER", "../RUN", "RUN?token", "A" * 120):
            with self.subTest(run=run), self.assertRaisesRegex(ValueError, "run_id"):
                validate_capture("detect", self._capture(run_id=run))
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_capture("detect", self._capture(captured_at="2026-10-22T20:00:00"))

    def test_safe_metadata_is_still_not_runtime_authentication(self):
        result = validate_capture("detect", self._capture(
            source_url="http://localhost:3000/d/acme-star?from=now-5m&to=now"))
        self.assertTrue(result["metadata_complete"])
        self.assertFalse(result["verified_real_capture"])

    def test_malformed_untrusted_shapes_fail_closed_with_value_errors(self):
        for state in ([], {}, {"nested": []}):
            with self.subTest(proof_state=state), self.assertRaisesRegex(
                ValueError, "invalid proof state"
            ):
                validate_capture("detect", self._capture(proof_state=state))

        with self.assertRaisesRegex(ValueError, "unknown cue"):
            validate_capture([], self._capture())

        for record in ([], None):
            with self.subTest(record=record), self.assertRaisesRegex(
                ValueError, "capture record must be an object"
            ):
                validate_capture("detect", record)

        with self.assertRaisesRegex(ValueError, "capture record must be an object"):
            build_timeline({"detect": []})

    def test_unknown_cue_refused(self):
        with self.assertRaises(ValueError):
            build_timeline({"undocumented": {}})

if __name__ == "__main__":
    unittest.main()
