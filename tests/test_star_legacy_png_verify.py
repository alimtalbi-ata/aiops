import hashlib
import struct
import zlib
import tempfile
import unittest
from pathlib import Path
from demo.star_legacy_png_verify import verify_legacy_pngs

class LegacyPngVerify(unittest.TestCase):
    def _sample(self):
        # Structurally valid 1x1 synthetic PNG, not a screenshot or runtime proof.
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        pixels = zlib.compress(b"\x00\x00\x00\x00")
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    def test_byte_match_never_authenticates_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"grafana.png";data=self._sample();p.write_bytes(data)
            d={"browser":"Chromium","automation":"Playwright","captures":[
                {"name":"10-grafana","service":"Grafana","status":"PASS","file":"grafana.png",
                 "sha256":hashlib.sha256(data).hexdigest()}]}
            v=verify_legacy_pngs(d,Path(tmp))["entries"][0]
            self.assertTrue(v["integrity_verified"])
            self.assertFalse(v["runtime_authenticated"])
            self.assertFalse(v["business_state_verified"])
    def test_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/"grafana.png").write_bytes(self._sample())
            d={"browser":"Chromium","automation":"Playwright","captures":[
                {"name":"10-grafana","service":"Grafana","status":"PASS","file":"grafana.png",
                 "sha256":"a"*64}]}
            self.assertFalse(verify_legacy_pngs(d,Path(tmp))["entries"][0]["integrity_verified"])
    def test_escape_and_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"a.png").symlink_to(root/"target.png")
            d={"browser":"Chromium","automation":"Playwright","captures":[
                {"name":"a","service":"Grafana","status":"PASS","file":"a.png","sha256":"a"*64}]}
            self.assertFalse(verify_legacy_pngs(d,root)["entries"][0]["capture_file_available"])
    def test_duplicate_filename_cannot_claim_second_verified_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=self._sample()
            (Path(tmp)/"shared.png").write_bytes(data)
            h=hashlib.sha256(data).hexdigest()
            d={"browser":"Chromium","automation":"Playwright","captures":[
                {"name":"08-glpi","service":"GLPI","status":"PASS","file":"shared.png","sha256":h},
                {"name":"09-n8n","service":"n8n","status":"PASS","file":"shared.png","sha256":h}]}
            items=verify_legacy_pngs(d,Path(tmp))["entries"]
            self.assertTrue(items[0]["integrity_verified"])
            self.assertFalse(items[1]["integrity_verified"])
            self.assertEqual(items[1]["migration_note"],"duplicate_filename")
    def test_failed_legacy_capture_never_qualifies_even_with_matching_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=self._sample()
            (Path(tmp)/"failed.png").write_bytes(data)
            d={"browser":"Chromium","automation":"Playwright","captures":[
                {"name":"08-glpi","service":"GLPI","status":"FAIL",
                 "file":"failed.png","sha256":hashlib.sha256(data).hexdigest()}]}
            entry=verify_legacy_pngs(d,Path(tmp))["entries"][0]
            self.assertFalse(entry["integrity_verified"])
            self.assertEqual(entry["migration_note"],"legacy_capture_failed")
if __name__=="__main__":unittest.main()
