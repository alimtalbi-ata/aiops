"""Synthetic-only, offline time alignment qualification. No runtime network."""
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from demo.star_event_capture_alignment import verify_event_capture_alignment

RUN = "RUN-STAR-TEMP-001"
CORR = "CORR-STAR-TEMP-001"
EVENT = "DASHBOARD-01"
CAPTURE = "2026-10-23T18:00:30+00:00"


def png():
    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


class EventCaptureAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        image = png()
        (self.root / "detect.png").write_bytes(image)
        self.expected = {"run_id": RUN, "correlation_id": CORR, "events": {"detect": EVENT}}
        self.manifest = {
            "schema": "star-browser-evidence/v1", "cue": "detect", "service": "grafana",
            "view": "alert_dashboard", "run_id": RUN, "correlation_id": CORR, "event_ref": EVENT,
            "expected_state": "firing", "observed_state": "firing", "captured_at": CAPTURE,
            "sha256": hashlib.sha256(image).hexdigest(), "screenshot_file": "detect.png",
            "provenance": "ISOLATED_TEST_FIXTURE", "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP",
            "anonymization": "SELECTOR_MASKS_UNREVIEWED",
            "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF",
            "source_url_redacted": "{origin}/d/{dashboard_uid}/{slug_redacted}",
            "event_time_alignment": "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP",
            "runtime_page_authenticated": False, "business_outcome_verified": False,
            "human_approval_authenticated": False,
        }
        self.anchor = {
            "run_id": RUN, "correlation_id": CORR, "event_ref": EVENT,
            "event_at": "2026-10-23T18:00:00Z", "source_kind": "ISOLATED_FIXTURE_EVENT",
            "source_sha256": "b" * 64,
        }
        self.write_manifest()

    def write_manifest(self):
        (self.root / "detect.json").write_text(json.dumps(self.manifest))

    def verify(self, anchor=None, **kwargs):
        return verify_event_capture_alignment(self.root, self.expected, ["detect.json"],
                                              {"detect": self.anchor if anchor is None else anchor}, **kwargs)

    def test_fixture_consistency_never_authenticates_runtime(self):
        report = self.verify()
        self.assertEqual(report["alignment"], "CONSISTENT_UNAUTHENTICATED")
        self.assertEqual(report["entries"][0]["lag_seconds"], 30)
        self.assertEqual(report["entries"][0]["provenance"], "SYNTHETIC")
        self.assertFalse(report["runtime_authenticated"])
        self.assertFalse(report["business_validated"])
        self.assertFalse(report["independent_event_source_authenticated"])

    def test_operator_provenance_stays_unreviewed(self):
        self.manifest["provenance"] = "OPERATOR_BROWSER_UNREVIEWED"
        self.manifest["capture_transport"] = "READ_ONLY_BROWSER_HTTP_GET"
        self.write_manifest()
        result = self.verify({**self.anchor, "source_kind": "OPERATOR_EVENT_LOG_UNREVIEWED"})
        self.assertEqual(result["entries"][0]["provenance"], "OPERATOR_UNREVIEWED")
        self.assertFalse(result["human_approval_authenticated"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_rejects_missing_or_extra_event_anchor(self):
        for anchors in ({}, {"detect": self.anchor, "ticket": self.anchor}):
            with self.subTest(anchors=anchors), self.assertRaises(ValueError):
                verify_event_capture_alignment(self.root, self.expected, ["detect.json"], anchors)

    def test_rejects_contradictory_identity(self):
        for field in ("run_id", "correlation_id", "event_ref"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify({**self.anchor, field: "WRONG-IDENTITY"})

    def test_rejects_cross_provenance_and_extra_fields(self):
        for change in ({"source_kind": "OPERATOR_EVENT_LOG_UNREVIEWED"}, {"approved": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify({**self.anchor, **change})

    def test_rejects_naive_timestamp_and_missing_digest(self):
        for change in ({"event_at": "2026-10-23T18:00:00"}, {"source_sha256": "bad"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify({**self.anchor, **change})

    def test_rejects_outside_event_window(self):
        for event_time in ("2026-10-23T17:57:00Z", "2026-10-23T18:00:40Z"):
            with self.subTest(event_time=event_time), self.assertRaises(ValueError):
                self.verify({**self.anchor, "event_at": event_time})

    def test_tolerates_bounded_clock_skew(self):
        self.assertEqual(self.verify({**self.anchor, "event_at": "2026-10-23T18:00:32Z"})["entries"][0]["lag_seconds"], -2)

    def test_rejects_duplicate_manifest_json_keys(self):
        path = self.root / "detect.json"
        path.write_text(path.read_text().replace('"cue": "detect",', '"cue": "detect", "cue": "ticket",'))
        with self.assertRaises(ValueError):
            self.verify()

    def test_rejects_tampered_png(self):
        (self.root / "detect.png").write_bytes(b"not a png")
        with self.assertRaises(ValueError):
            self.verify()

    def test_rejects_unbounded_tolerances(self):
        for kw in ({"max_delay_seconds": 3601}, {"clock_skew_seconds": 11}, {"max_delay_seconds": True}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.verify(**kw)

    def test_requires_capture_manifest(self):
        with self.assertRaises(ValueError):
            verify_event_capture_alignment(self.root, self.expected, [], {})


if __name__ == "__main__":
    unittest.main()
