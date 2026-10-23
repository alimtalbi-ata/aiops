import hashlib
import tempfile
import unittest
from pathlib import Path
from demo.star_capture_evidence import verify_manifest

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

    def test_synthetic_cannot_be_claimed_as_real(self):
        with self.assertRaises(ValueError):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "proof_state": "simulated", "claim_real": True}
            })

if __name__ == "__main__":
    unittest.main()
