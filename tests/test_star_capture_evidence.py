import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from demo.star_capture_evidence import verify_file, verify_manifest

# Structurally complete SYNTHETIC PNG, not a browser/runtime screenshot.
import struct
import zlib

def _chunk(kind, payload=b""):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

PNG = (b"\x89PNG\r\n\x1a\n" +
       _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
       _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + _chunk(b"IEND"))

class CaptureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "evidence").mkdir()
        (self.root / "evidence/alert.png").write_bytes(PNG)
        self.record = {
            "service": "grafana", "view": "alert_dashboard",
            "proof_state": "captured", "run_id": "ACME-TEST-001",
            "source_url": "http://localhost:3000/d/demo",
            "captured_at": "2026-10-23T10:00:00+02:00",
            "screenshot_path": "evidence/alert.png",
            "sha256": hashlib.sha256(PNG).hexdigest(),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_integrity_is_not_runtime_proof(self):
        result = verify_manifest(self.root, "ACME-TEST-001", {"detect": self.record})
        self.assertEqual(result["entries"][0]["status"], "integrity_checked")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["integrity_checked"])

    def test_tampered_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "sha256": "0" * 64}
            })

    def test_run_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cross-run"):
            verify_manifest(self.root, "OTHER-001", {"detect": self.record})

    def test_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "screenshot_path": "evidence/../alert.png"}
            })

    def test_valid_sha_but_malformed_png_rejected(self):
        malformed = PNG[:-12]
        (self.root / "evidence/alert.png").write_bytes(malformed)
        with self.assertRaisesRegex(ValueError, "IEND"):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "sha256": hashlib.sha256(malformed).hexdigest()}
            })

    def test_same_png_cannot_prove_two_distinct_scenes(self):
        # Different filenames/metadata are insufficient if bytes are identical.
        (self.root / "evidence/second.png").write_bytes(PNG)
        ticket = {**self.record, "service": "glpi", "view": "incident_ticket",
                  "source_url": "http://localhost:8080/front/ticket.form.php?id=123",
                  "screenshot_path": "evidence/second.png",
                  "captured_at": "2026-10-23T10:00:30+02:00"}
        with self.assertRaisesRegex(ValueError, "reused"):
            verify_manifest(self.root, "ACME-TEST-001", {"detect": self.record, "ticket": ticket})

    def test_synthetic_cannot_be_claimed_as_real(self):
        with self.assertRaises(ValueError):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "proof_state": "simulated", "claim_real": True}
            })

    def test_manifest_reader_rejects_duplicate_keys_at_any_depth(self):
        path = self.root / "manifest.json"
        payloads = (
            '{"run_id":"ACME-TEST-001","run_id":"OTHER-TEST-001","captures":{}}',
            '{"run_id":"ACME-TEST-001","captures":{"detect":{"cue":"detect","cue":"ticket"}}}',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                path.write_text(payload, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "duplicate evidence manifest JSON key"):
                    verify_file(path, self.root)

    def test_manifest_reader_refuses_symlinks_and_oversized_files(self):
        target = self.root / "target.json"
        target.write_text('{"run_id":"ACME-TEST-001","captures":{}}', encoding="utf-8")
        link = self.root / "linked-manifest.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            verify_file(link, self.root)

        oversized = self.root / "oversized.json"
        oversized.write_bytes(b" " * 300_001)
        with self.assertRaisesRegex(ValueError, "too large"):
            verify_file(oversized, self.root)

    def test_manifest_reader_refuses_invalid_utf8_and_non_object_records(self):
        path = self.root / "manifest.json"
        path.write_bytes(bytes([255]))
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            verify_file(path, self.root)

        path.write_text(
            json.dumps({"run_id": "ACME-TEST-001", "captures": {"detect": []}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "capture record must be an object"):
            verify_file(path, self.root)

if __name__ == "__main__":
    unittest.main()
