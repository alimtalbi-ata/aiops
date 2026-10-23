import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from demo.star_portal_transport import export_storyboard
from demo.star_png_integrity import PNG_SIGNATURE
import struct
import zlib

# Complete synthetic PNG; no browser or runtime evidence is claimed.
def _chunk(kind, payload=b""):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

PNG = (PNG_SIGNATURE +
       _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
       _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) +
       _chunk(b"IEND"))

class PortalTransportTests(unittest.TestCase):
    def test_export_nine_cues_without_claiming_browser_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"evidence").mkdir()
            (root/"evidence"/"a.png").write_bytes(PNG)
            manifest = root/"manifest.json"
            manifest.write_text(json.dumps({
                "run_id":"STAR-ACME-001",
                "captures":{"detect":{
                    "service":"grafana", "view":"alert_dashboard",
                    "proof_state":"captured", "run_id":"STAR-ACME-001",
                    "source_url":"http://localhost:3000/d/acme",
                    "captured_at":"2026-10-23T10:00:00+02:00",
                    "screenshot_path":"evidence/a.png",
                    "sha256":hashlib.sha256(PNG).hexdigest()
                }}
            }))
            data=export_storyboard(manifest,root,"SAN_FABRIC_P1")
            self.assertEqual(len(data["frames"]),9)
            self.assertEqual(data["frames"][0]["capture_status"],"integrity_checked")
            self.assertFalse(data["safety"]["runtime_authenticated"])
            self.assertTrue(data["safety"]["read_only"])
            self.assertTrue(all(not f["action_allowed"] for f in data["frames"]))

    def test_invalid_scenario_fails(self):
        with self.assertRaises(ValueError):
            from demo.star_portal_storyboard import storyboard
            storyboard({"schema":"star-capture-evidence-v1","entries":[]},"LIVE")

if __name__ == "__main__":
    unittest.main()
