import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_offline_manifest_v2128 import verify, REQUIRED


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        entries = []
        for name in sorted(REQUIRED):
            content = ("offline:" + name).encode()
            (self.root / name).write_bytes(content)
            entries.append({"name": name, "sha256": hashlib.sha256(content).hexdigest()})
        self.manifest = {"version": "2.12.4", "mode": "OFFLINE_MIXED_SEPARATED",
                         "historical_source": "OPERATOR_SUPPLIED_SUMMARY_NOT_INDEPENDENTLY_AUTHENTICATED",
                         "dgx_independently_attested": False,
                         "live_execution_qualified": False, "files": entries}
        self.save()

    def save(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def reject(self):
        with self.assertRaises((ValueError, OSError)):
            verify(self.root)

    def test_valid(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["dgx_independently_attested"])

    def test_tampered(self):
        (self.root / "index.html").write_text("tampered")
        self.reject()

    def test_missing(self):
        (self.root / "index.html").unlink()
        self.reject()

    def test_duplicate(self):
        self.manifest["files"].append(self.manifest["files"][0].copy())
        self.save()
        self.reject()

    def test_traversal(self):
        self.manifest["files"][0]["name"] = "../outside.html"
        self.save()
        self.reject()

    def test_symlink(self):
        (self.root / "index.html").unlink()
        (self.root / "index.html").symlink_to("/etc/hosts")
        self.reject()

    def test_unlisted(self):
        (self.root / "surprise.txt").write_text("unlisted")
        self.reject()

    def test_false_attestation(self):
        self.manifest["live_execution_qualified"] = True
        self.save()
        self.reject()

    def test_bad_digest(self):
        self.manifest["files"][0]["sha256"] = "not-a-digest"
        self.save()
        self.reject()

    def test_missing_entry(self):
        self.manifest["files"].pop()
        self.save()
        self.reject()


if __name__ == "__main__":
    unittest.main()
