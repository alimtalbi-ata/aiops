"""Offline synthetic contract for Chromium manifest -> STAR storyboard."""
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from demo.star_browser_manifest_gate import verify_browser_manifests
from demo.star_portal_storyboard import storyboard


def chunk(kind, data=b""):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND"))
EXPECTED = {"run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001", "events": {"detect": "DASH-7"}}


class BrowserManifestGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "detect.png").write_bytes(PNG)
        self.item = {"schema": "star-browser-evidence/v1", "cue": "detect", "service": "grafana",
                     "view": "alert_dashboard", "run_id": "RUN-ACME-001", "correlation_id": "CORR-ACME-001",
                     "event_ref": "DASH-7", "expected_state": "firing", "observed_state": "firing",
                     "captured_at": "2026-10-23T11:00:00+00:00", "sha256": hashlib.sha256(PNG).hexdigest(),
                     "screenshot_file": "detect.png", "provenance": "ISOLATED_TEST_FIXTURE",
                     "capture_transport": "LOCAL_HTML_FIXTURE_NO_HTTP",
                     "anonymization": "SELECTOR_MASKS_UNREVIEWED",
                     "qualification": "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF"}
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        (self.root / "detect.json").write_text(json.dumps(self.item), encoding="utf-8")

    def run_gate(self):
        return verify_browser_manifests(self.root, EXPECTED, ["detect.json"])

    def test_fixture_remains_simulated_and_storyboard_compatible(self):
        report = self.run_gate()
        self.assertEqual(report["entries"][0]["status"], "simulated")
        self.assertFalse(report["runtime_authenticated"])
        self.assertFalse(report["integrity_checked"])
        frames = storyboard(report, "SAN_FABRIC_P1")["frames"]
        self.assertEqual(frames[0]["capture_status"], "simulated")
        self.assertEqual(frames[1]["capture_status"], "missing")

    def test_operator_manifest_is_only_integrity_checked(self):
        self.item["provenance"] = "OPERATOR_BROWSER_UNREVIEWED"
        self.item["capture_transport"] = "READ_ONLY_BROWSER_HTTP_GET"
        self.write()
        report = self.run_gate()
        self.assertEqual(report["entries"][0]["status"], "integrity_checked")
        self.assertFalse(report["runtime_authenticated"])

    def test_identity_conflicts_rejected(self):
        for key in ("run_id", "correlation_id", "event_ref"):
            with self.subTest(key=key):
                old = self.item[key]
                self.item[key] = "WRONG-123"
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.item[key] = old

    def test_claims_tampering_and_state_rejected(self):
        for key, value in (("sha256", "0" * 64), ("observed_state", "recovered"),
                           ("business_validated", True), ("verified_real_capture", True),
                           ("anonymization", "VERIFIED")):
            with self.subTest(key=key):
                old = self.item.get(key)
                self.item[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                if old is None:
                    self.item.pop(key)
                else:
                    self.item[key] = old

    def test_paths_and_symlinks_rejected(self):
        for name in ("../detect.png", "/tmp/detect.png", "sub/detect.png"):
            with self.subTest(name=name):
                self.item["screenshot_file"] = name
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
        self.item["screenshot_file"] = "link.png"
        (self.root / "link.png").symlink_to(self.root / "detect.png")
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_missing_expected_identity_rejected(self):
        with self.assertRaises(ValueError):
            verify_browser_manifests(self.root, {**EXPECTED, "events": {}}, ["detect.json"])

    def test_duplicate_manifest_rejected(self):
        with self.assertRaises(ValueError):
            verify_browser_manifests(self.root, EXPECTED, ["detect.json", "detect.json"])

    def test_transport_contradiction_rejected(self):
        self.item["capture_transport"] = "READ_ONLY_BROWSER_HTTP_GET"
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_unexpected_fields_and_unredacted_url_rejected(self):
        for key, value in (("secret", "do-not-publish"),
                           ("runtime_validated", True),
                           ("source_url_redacted", "http://localhost:8080/front/ticket.form.php?id=441"),
                           ("source_url_redacted", "{origin}/unexpected/path"),
                           ("event_time_alignment", "VERIFIED")):
            with self.subTest(key=key, value=value):
                self.item[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.item.pop(key)
        self.item["source_url_redacted"] = "{origin}/d/{dashboard_uid}/{slug_redacted}"
        self.item["event_time_alignment"] = "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP"
        self.write()
        self.assertEqual(self.run_gate()["entries"][0]["status"], "simulated")

    def test_naive_timestamp_rejected(self):
        self.item["captured_at"] = "2026-10-23T11:00:00"
        self.write()
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_cue_order_chronology_rejected_even_when_input_reversed(self):
        other_png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND"))
        (self.root / "verify.png").write_bytes(other_png)
        other = {**self.item, "cue": "verify", "view": "recovery_dashboard",
                 "expected_state": "recovered", "observed_state": "recovered",
                 "event_ref": "DASH-8", "screenshot_file": "verify.png",
                 "sha256": hashlib.sha256(other_png).hexdigest(),
                 "captured_at": "2026-10-23T10:00:00+00:00"}
        (self.root / "verify.json").write_text(json.dumps(other), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chronology"):
            verify_browser_manifests(self.root, {**EXPECTED, "events": {"detect": "DASH-7", "verify": "DASH-8"}},
                                     ["verify.json", "detect.json"])


if __name__ == "__main__":
    unittest.main()
