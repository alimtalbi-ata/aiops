"""Offline PNG structural qualification regression, stacked on #761.

An IHDR-only prefix is NOT a decodable PNG. This test documents a known
fail-open in the byte gate without claiming browser provenance or CI success.
"""
import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from noc_capture_integrity_gate import qualify

SHA = "a" * 40
WIDTHS = (320, 768, 1440)


def chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)


def png(width):
    # One row of opaque black pixels; fully encoded and CRC-protected.
    raw = b"\x00" + b"\x00\x00\x00" * width
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, 1, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PNGStructuralBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.manifest = {"source_sha": SHA, "mode": "SIMULATION",
                         "policy": "DENY_LIVE", "hitl": "REQUIRED", "captures": []}
        for width in WIDTHS:
            self.write(width, png(width))
            self.manifest["captures"].append({
                "viewport_width": width, "file": f"noc-{width}.png",
                "sha256": hashlib.sha256(png(width)).hexdigest(),
                "unknown_visible": True, "deny_live_visible": True,
                "no_horizontal_overflow": True, "external_requests_blocked": True})

    def write(self, width, data):
        (self.root / f"noc-{width}.png").write_bytes(data)

    def replace(self, width, data):
        self.write(width, data)
        for item in self.manifest["captures"]:
            if item["viewport_width"] == width:
                item["sha256"] = hashlib.sha256(data).hexdigest()

    def test_valid_encoded_png_fixture_accepted(self):
        self.assertEqual(qualify(self.manifest, self.root, SHA), [])

    def test_hash_mismatch_rejected(self):
        self.write(320, b"corrupt")
        self.assertTrue(qualify(self.manifest, self.root, SHA))

    @unittest.expectedFailure
    def test_incomplete_ihdr_only_png_must_be_rejected(self):
        # Known defect: existing gate checks only first 24 bytes.
        incomplete = png(320)[:24]
        self.replace(320, incomplete)
        self.assertTrue(qualify(self.manifest, self.root, SHA),
                        "IHDR-only bytes must not qualify as a real PNG")

    @unittest.expectedFailure
    def test_invalid_idat_crc_must_be_rejected(self):
        data = bytearray(png(320))
        data[-16] ^= 1  # Tamper with IDAT CRC while keeping IHDR and dimensions.
        self.replace(320, bytes(data))
        self.assertTrue(qualify(self.manifest, self.root, SHA),
                        "CRC-corrupted PNG must not qualify")


if __name__ == "__main__":
    unittest.main()
