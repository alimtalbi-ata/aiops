import hashlib
import tempfile
import unittest
from pathlib import Path
from demo.star_legacy_png_verify import verify_legacy_pngs

class LegacyPngVerify(unittest.TestCase):
    def _sample(self):
        # Minimal signature and trailer fixture, not a rendered or runtime PNG.
        return b"\x89PNG\r\n\x1a\n" + b"FICTIVE_FILE_BYTES" + b"IEND" + b"\x00"*4
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
if __name__=="__main__":unittest.main()
