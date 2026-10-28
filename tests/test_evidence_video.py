import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / "demo" / "evidence_video.py"
spec = importlib.util.spec_from_file_location("evidence_video", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EvidenceVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.entries = []
        for service in module.SERVICES:
            def chunk(kind, payload):
                return (struct.pack(">I", len(payload)) + kind + payload +
                        struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
            ihdr = struct.pack(">II", 320, 200) + bytes((8, 2, 0, 0, 0))
            scanlines = (bytes((0,)) + bytes(320 * 3)) * 200
            data = (module.PNG + chunk(b"IHDR", ihdr) +
                    chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))
            (self.root / (service + ".png")).write_bytes(data)
            self.entries.append({"service": service, "file": service + ".png",
                                 "sha256": hashlib.sha256(data).hexdigest(),
                                 "captured_at_utc": "2026-10-27T19:00:00Z",
                                 "source_url": "http://example.invalid/" + service})
    def manifest(self):
        return {"schema_version": 1, "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                "captures": self.entries}
    def test_five_present(self):
        self.assertEqual(len(module.verify(self.root, self.manifest())), 5)
    def test_missing_service_rejected(self):
        self.entries.pop()
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())
    def test_modified_file_rejected(self):
        (self.root / "n8n.png").write_bytes(b"modified")
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())
    def test_traversal_rejected(self):
        self.entries[0]["file"] = "../portal.png"
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())
    def test_duplicate_rejected(self):
        self.entries[1]["service"] = "portal"
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())
    def test_service_file_alias_rejected_even_with_valid_hash(self):
        # The technical fixtures intentionally have identical bytes. A receipt
        # may not reuse thruk.png to claim it is a portal screenshot.
        self.entries[0]["file"] = "thruk.png"
        with self.assertRaisesRegex(ValueError, "filename mismatch"):
            module.verify(self.root, self.manifest())

    def test_secret_bearing_or_noncanonical_source_urls_rejected(self):
        for url in (
            "https://example.invalid/portal?token=secret",
            "https://example.invalid/portal#access-token",
            "https://example.invalid/a/../portal",
            "https://example.invalid/portal\\\\secret",
            "https://example.invalid/portal path",
            "https://EXAMPLE.invalid/portal",
            "https://example.invalid.:443/portal",
            "https://example.invalid:99999/portal",
        ):
            with self.subTest(url=url):
                self.entries[0]["source_url"] = url
                with self.assertRaisesRegex(ValueError, "expose secrets"):
                    module.verify(self.root, self.manifest())

    def test_invalid_crc_rejected(self):
        path = self.root / "portal.png"
        data = bytearray(path.read_bytes())
        data[-5] ^= 1
        path.write_bytes(data)
        self.entries[0]["sha256"] = hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())

    def _replace_png(self, service, *, raw=None, idat_suffix=b"", extra_chunk=None, interlace=None):
        path = self.root / (service + ".png")
        data = path.read_bytes()
        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload +
                    struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
        ihdr = data[16:29]
        if interlace is not None:
            ihdr = ihdr[:-1] + bytes((interlace,))
        if raw is None:
            raw = (bytes((0,)) + bytes(320 * 3)) * 200
        replacement = (module.PNG + chunk(b"IHDR", ihdr) +
                       (chunk(*extra_chunk) if extra_chunk else b"") +
                       chunk(b"IDAT", zlib.compress(raw) + idat_suffix) +
                       chunk(b"IEND", b""))
        path.write_bytes(replacement)
        self.entries[module.SERVICES.index(service)]["sha256"] = hashlib.sha256(replacement).hexdigest()

    def test_corrupt_zlib_with_valid_chunk_crc_rejected(self):
        self._replace_png("portal", raw=b"not a valid image")
        with self.assertRaisesRegex(ValueError, "pixels"):
            module.verify(self.root, self.manifest())

    def test_invalid_png_filter_with_valid_crc_rejected(self):
        self._replace_png("portal", raw=(bytes((5,)) + bytes(320 * 3)) * 200)
        with self.assertRaisesRegex(ValueError, "pixels"):
            module.verify(self.root, self.manifest())

    def test_extra_compressed_bytes_rejected(self):
        self._replace_png("portal", idat_suffix=b"trailing-compressed-data")
        with self.assertRaisesRegex(ValueError, "pixels"):
            module.verify(self.root, self.manifest())

    def test_png_text_metadata_rejected(self):
        self._replace_png("portal", extra_chunk=(b"tEXt", b"Authorization\\x00Bearer-secret"))
        with self.assertRaisesRegex(ValueError, "metadata"):
            module.verify(self.root, self.manifest())

    def test_interlaced_png_rejected(self):
        self._replace_png("portal", interlace=1)
        with self.assertRaisesRegex(ValueError, "pixels"):
            module.verify(self.root, self.manifest())

    def test_rgba_png_accepted(self):
        self._replace_png("portal", raw=(bytes((0,)) + bytes(320 * 4)) * 200)
        # The image format must also declare RGBA, not just have RGBA-sized scanlines.
        path = self.root / "portal.png"
        data = path.read_bytes()
        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload +
                    struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
        rgba = module.PNG + chunk(b"IHDR", struct.pack(">II", 320, 200) + bytes((8, 6, 0, 0, 0)))
        rgba += data[33:]
        path.write_bytes(rgba)
        self.entries[0]["sha256"] = hashlib.sha256(rgba).hexdigest()
        self.assertEqual(len(module.verify(self.root, self.manifest())), 5)

    def test_bad_timestamp_rejected(self):
        self.entries[0]["captured_at_utc"] = "yesterdayZ"
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())

    def test_url_credentials_rejected(self):
        self.entries[0]["source_url"] = "https://admin:password@example.invalid/"
        with self.assertRaises(ValueError):
            module.verify(self.root, self.manifest())

    def test_no_runtime_attestation(self):
        self.assertTrue(all(x["status"] == "BYTES_HASH_VERIFIED_NOT_RUNTIME_ATTESTED"
                            for x in module.verify(self.root, self.manifest())))

if __name__ == "__main__":
    unittest.main()
