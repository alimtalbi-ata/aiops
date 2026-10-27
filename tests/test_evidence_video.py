import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

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
            data = module.PNG + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 1920, 1080) + b"\x08\x02\x00\x00\x00" + b"0" * 32
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
    def test_no_runtime_attestation(self):
        self.assertTrue(all(x["status"] == "BYTES_HASH_VERIFIED_NOT_RUNTIME_ATTESTED"
                            for x in module.verify(self.root, self.manifest())))

if __name__ == "__main__":
    unittest.main()
