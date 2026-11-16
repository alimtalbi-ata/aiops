"""Offline regression tests for NOC capture-byte gate; no browser or network."""
import copy
import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from noc_capture_integrity_gate import qualify

SHA = "a" * 40
WIDTHS = (320, 768, 1440)


class CaptureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.manifest = {
            "source_sha": SHA, "mode": "SIMULATION",
            "policy": "DENY_LIVE", "hitl": "REQUIRED", "captures": []
        }
        for width in WIDTHS:
            # Header-only synthetic bytes test the gate, not PNG decoding or Chromium.
            raw = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, 700)
            name = f"noc-{width}.png"
            (self.root / name).write_bytes(raw)
            self.manifest["captures"].append({
                "viewport_width": width, "file": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "unknown_visible": True, "deny_live_visible": True,
                "no_horizontal_overflow": True, "external_requests_blocked": True
            })

    def test_synthetic_byte_fixture_is_accepted_not_browser_attested(self):
        self.assertEqual(qualify(self.manifest, self.root, SHA), [])

    def test_live_mode_denied(self):
        self.manifest["mode"] = "LIVE"
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_policy_and_hitl_fail_closed(self):
        self.manifest["policy"] = "ALLOW"
        self.manifest["hitl"] = "APPROVED"
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_wrong_sha_denied(self):
        self.assertTrue(qualify(self.manifest, self.root, "b" * 40))

    def test_corrupted_capture_denied(self):
        (self.root / "noc-320.png").write_bytes(b"not a PNG")
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_duplicate_viewport_denied(self):
        self.manifest["captures"][1]["viewport_width"] = 320
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_unverified_safety_assertion_denied(self):
        self.manifest["captures"][0]["external_requests_blocked"] = None
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_traversal_denied(self):
        self.manifest["captures"][0]["file"] = "../outside.png"
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    def test_missing_capture_denied(self):
        (self.root / "noc-768.png").unlink()
        self.assertTrue(qualify(self.manifest, self.root, SHA))


if __name__ == "__main__":
    unittest.main()
