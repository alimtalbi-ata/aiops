"""Synthetic byte-level PNG adversarial tests; never runtime screenshots."""
import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from demo.star_png_integrity import inspect_png

def chunk(kind, data=b""):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

def png(*, width=1, height=1, depth=8, color=2, chunks=None):
    header = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0)
    if chunks is None:
        chunks = [chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))]
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + b"".join(chunks) + chunk(b"IEND")

class StrictPngIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "capture.png"

    def check(self, data):
        self.path.write_bytes(data)
        return inspect_png(self.path)

    def test_valid_synthetic_png_integrity_only(self):
        sample = png()
        self.assertEqual(self.check(sample), (hashlib.sha256(sample).hexdigest(), len(sample)))

    def test_valid_png_with_ancillary_chunk(self):
        sample = png(chunks=[chunk(b"pHYs", b"\x00" * 9), chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))])
        self.assertEqual(self.check(sample)[1], len(sample))

    def test_reject_fake_signature_only_fixture(self):
        with self.assertRaises(ValueError):
            self.check(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"\x00" * 17)

    def test_reject_crc_tampering(self):
        sample = bytearray(png())
        sample[29] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC"):
            self.check(sample)

    def test_reject_missing_iend(self):
        with self.assertRaises(ValueError):
            self.check(png()[:-12])

    def test_reject_trailing_bytes(self):
        with self.assertRaisesRegex(ValueError, "trailing"):
            self.check(png() + b"SECRET")

    def test_reject_embedded_text_metadata(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.check(png(chunks=[chunk(b"tEXt", b"token\x00secret"), chunk(b"IDAT", b"123")]))

    def test_reject_excessive_dimensions(self):
        with self.assertRaises(ValueError):
            self.check(png(width=50000))
        with self.assertRaises(ValueError):
            self.check(png(width=16000, height=16000))

    def test_reject_unknown_critical_chunk(self):
        with self.assertRaisesRegex(ValueError, "critical"):
            self.check(png(chunks=[chunk(b"ABCD", b"123"), chunk(b"IDAT", b"123")]))

    def test_reject_discontinuous_idat(self):
        with self.assertRaisesRegex(ValueError, "IDAT"):
            self.check(png(chunks=[chunk(b"IDAT", b"1"), chunk(b"pHYs", b"123"), chunk(b"IDAT", b"2")]))

    def test_reject_duplicate_ihdr(self):
        with self.assertRaises(ValueError):
            self.check(png(chunks=[chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)), chunk(b"IDAT", b"1")]))

    def test_indexed_png_requires_palette_before_idat(self):
        with self.assertRaisesRegex(ValueError, "requires PLTE"):
            self.check(png(depth=1, color=3))

    def test_valid_indexed_png_palette_respects_bit_depth(self):
        sample = png(depth=1, color=3, chunks=[
            chunk(b"PLTE", b"\x00\x00\x00\xff\xff\xff"),
            chunk(b"IDAT", zlib.compress(b"\x00\x00")),
        ])
        self.assertEqual(self.check(sample)[1], len(sample))

    def test_indexed_png_palette_cannot_exceed_bit_depth(self):
        sample = png(depth=1, color=3, chunks=[
            chunk(b"PLTE", b"\x00\x00\x00" * 3),
            chunk(b"IDAT", zlib.compress(b"\x00\x00")),
        ])
        with self.assertRaisesRegex(ValueError, "exceeds indexed bit depth"):
            self.check(sample)

    def test_grayscale_png_forbids_palette(self):
        for color in (0, 4):
            with self.subTest(color=color):
                sample = png(color=color, chunks=[
                    chunk(b"PLTE", b"\x00\x00\x00"),
                    chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")),
                ])
                with self.assertRaisesRegex(ValueError, "forbidden for grayscale"):
                    self.check(sample)

    def test_reject_invalid_png_size_limit(self):
        self.path.write_bytes(png())
        with self.assertRaises(ValueError):
            inspect_png(self.path, max_bytes=20)

    def test_reject_missing_idat(self):
        with self.assertRaises(ValueError):
            self.check(png(chunks=[]))

    def test_reject_non_png(self):
        with self.assertRaises(ValueError):
            self.check(b"NOT PNG" * 20)

    def test_refuse_final_symlink_instead_of_hashing_target(self):
        target = self.path.with_name("other.png")
        target.write_bytes(png())
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink|safely"):
            inspect_png(self.path)

    def test_fail_closed_when_nofollow_primitive_is_unavailable(self):
        self.path.write_bytes(png())
        with patch("demo.star_png_integrity.os.O_NOFOLLOW", None, create=True):
            with self.assertRaisesRegex(ValueError, "without O_NOFOLLOW"):
                inspect_png(self.path)

    def test_refuse_non_regular_input(self):
        with self.assertRaisesRegex(ValueError, "regular file"):
            inspect_png(self.path.parent)

if __name__ == "__main__":
    unittest.main()
