"""Synthetic fixtures only: source-byte SHA binding is not runtime authentication."""
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from demo.star_event_source_binding import verify_event_source_binding


def png():
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


class SourceBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "events").mkdir()
        self.expected = {"run_id": "RUN-ACME-123", "correlation_id": "CORR-ACME-123",
                         "events": {"detect": "DASHBOARD-123"}}
        image = png()
        (self.root / "detect.png").write_bytes(image)
        self.manifest = {
            "schema": "star-browser-evidence/v1", "cue": "detect", "service": "grafana",
            "view": "alert_dashboard", "run_id": self.expected["run_id"],
            "correlation_id": self.expected["correlation_id"], "event_ref": "DASHBOARD-123",
            "expected_state": "firing", "observed_state": "firing",
            "captured_at": "2026-10-23T18:00:30Z", "sha256": hashlib.sha256(image).hexdigest(),
            "screenshot_file": "detect.png", "provenance": "ISOLATED_TEST_FIXTURE",
            "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP",
            "anonymization": "SELECTOR_MASKS_UNREVIEWED",
            "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF",
            "source_url_redacted": "{origin}/d/{dashboard_uid}/{slug_redacted}",
            "event_time_alignment": "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP",
            "runtime_page_authenticated": False, "business_outcome_verified": False,
            "human_approval_authenticated": False,
        }
        (self.root / "detect.json").write_text(json.dumps(self.manifest))
        self.event = {
            "schema": "star-event-source/v1", "cue": "detect", "service": "grafana",
            "view": "alert_dashboard", "run_id": self.expected["run_id"],
            "correlation_id": self.expected["correlation_id"], "event_ref": "DASHBOARD-123",
            "event_at": "2026-10-23T18:00:00+00:00", "source_kind": "ISOLATED_FIXTURE_EVENT",
            "observed_state": "firing", "source_event_id": "EVENT-123",
        }
        self.anchor = {
            "run_id": self.expected["run_id"], "correlation_id": self.expected["correlation_id"],
            "event_ref": "DASHBOARD-123", "event_at": "2026-10-23T18:00:00Z",
            "source_kind": "ISOLATED_FIXTURE_EVENT", "source_sha256": "",
        }
        self.write_event()

    def write_event(self):
        data = json.dumps(self.event, sort_keys=True).encode()
        (self.root / "events" / "detect.json").write_bytes(data)
        self.anchor["source_sha256"] = hashlib.sha256(data).hexdigest()

    def check(self, **kw):
        return verify_event_source_binding(self.root, self.expected, ["detect.json"],
                                           {"detect": self.anchor}, {"detect": "detect.json"}, **kw)

    def test_bytes_bound_but_not_authenticated(self):
        report = self.check()
        self.assertTrue(report["event_source_bytes_verified"])
        self.assertFalse(report["independent_event_source_authenticated"])
        self.assertFalse(report["runtime_authenticated"])
        self.assertFalse(report["business_validated"])
        self.assertFalse(report["live_remediation_authorized"])

    def test_rejects_tampered_bytes(self):
        path = self.root / "events" / "detect.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "SHA"):
            self.check()

    def test_rejects_forged_event_state_even_with_matching_digest(self):
        self.event["observed_state"] = "resolved"
        self.write_event()
        with self.assertRaisesRegex(ValueError, "state"):
            self.check()

    def test_rejects_contradictory_identity_even_with_matching_digest(self):
        self.event["run_id"] = "RUN-OTHER-123"
        self.write_event()
        with self.assertRaisesRegex(ValueError, "identity"):
            self.check()

    def test_rejects_contradictory_time_even_with_matching_digest(self):
        self.event["event_at"] = "2026-10-23T18:00:02Z"
        self.write_event()
        with self.assertRaisesRegex(ValueError, "timestamp"):
            self.check()

    def test_rejects_wrong_service_even_with_matching_digest(self):
        self.event["service"] = "glpi"
        self.write_event()
        with self.assertRaisesRegex(ValueError, "application"):
            self.check()

    def test_rejects_extra_attestation_field(self):
        self.event["human_approval_authenticated"] = True
        self.write_event()
        with self.assertRaisesRegex(ValueError, "schema"):
            self.check()

    def test_rejects_duplicate_json_keys(self):
        path = self.root / "events" / "detect.json"
        data = path.read_text().replace('"cue": "detect"', '"cue": "detect", "cue": "ticket"')
        path.write_text(data)
        self.anchor["source_sha256"] = hashlib.sha256(data.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()

    def test_rejects_event_file_symlink(self):
        path = self.root / "events" / "detect.json"
        path.unlink()
        path.symlink_to(self.root / "detect.json")
        with self.assertRaises(OSError):
            self.check()

    def test_rejects_events_directory_symlink(self):
        original = self.root / "events"
        original.rename(self.root / "events-real")
        original.symlink_to(self.root / "events-real", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.check()

    def test_rejects_filename_traversal(self):
        for filename in ("../detect.json", "/tmp/detect.json", "x/y.json", "detect.png"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                verify_event_source_binding(self.root, self.expected, ["detect.json"],
                                            {"detect": self.anchor}, {"detect": filename})

    def test_rejects_missing_file_and_extra_cue(self):
        for source_files in ({}, {"detect": "detect.json", "ticket": "extra.json"}):
            with self.subTest(source_files=source_files), self.assertRaises(ValueError):
                verify_event_source_binding(self.root, self.expected, ["detect.json"],
                                            {"detect": self.anchor}, source_files)

    def test_rejects_oversized_source(self):
        (self.root / "events" / "detect.json").write_bytes(b"A" * 65537)
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.check()


if __name__ == "__main__":
    unittest.main()
