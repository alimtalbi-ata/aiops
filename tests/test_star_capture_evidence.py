import hashlib
import tempfile
import unittest
from pathlib import Path
from demo.star_capture_evidence import verify_manifest

# Minimal PNG fixture with valid signature and IHDR dimensions; no browser claim.
PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" +
       b"\x00\x00\x00\x01\x00\x00\x00\x01" +
       b"\x08\x02\x00\x00\x00" + b"\x00\x00\x00\x00")

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

    def test_synthetic_cannot_be_claimed_as_real(self):
        with self.assertRaises(ValueError):
            verify_manifest(self.root, "ACME-TEST-001", {
                "detect": {**self.record, "proof_state": "simulated", "claim_real": True}
            })

if __name__ == "__main__":
    unittest.main()
