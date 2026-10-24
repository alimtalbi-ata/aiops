"""Isolated, synthetic ZIP fixtures: no prod services, ports or private data."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from recovery.tools.zip_source_recovery import inventory, recover


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.archive = self.root / "AIOPS-V2.13.4-SYNTHETIC.zip"
        self.dest = self.root / "quarantine"
        self.dest.mkdir()

    def make(self, files):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            for path, value in files:
                z.writestr(path, value)

    def test_inventory_sha_and_version(self):
        self.make([("tools/replay.py", "print('synthetic')\n")])
        m = inventory([self.archive])
        self.assertEqual(m["schema"], "aiops-zip-source-inventory/v1")
        self.assertEqual(m["members"][0]["version"], "2.13.4")
        self.assertEqual(m["members"][0]["member_sha256"], hashlib.sha256(b"print('synthetic')\n").hexdigest())
        self.assertEqual(m["members"][0]["python_syntax"], "parse_pass_not_completeness")
        self.assertFalse(m["complete_source_attested"])
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_compact_version_naming(self):
        self.archive = self.root / "AIOps-V21349-SYNTHETIC.zip"
        self.make([("module.py", "x=1\n")])
        self.assertEqual(inventory([self.archive])["members"][0]["version"], "2.13.49")

    def test_dedup_and_no_source_claim(self):
        self.make([("a.py", "x=1\n"), ("b.py", "x=1\n")])
        m = inventory([self.archive])["members"]
        self.assertIsNone(m[0]["duplicate_of"])
        self.assertEqual(m[1]["duplicate_of"]["path"], "a.py")
        self.assertTrue(all(x["reuse_status"] == "quarantine_review_required" for x in m))

    def test_unsafe_paths_rejected(self):
        for name in ("../outside.py", "/tmp/outside.py", "a/../b.py", "C:/a.py", "a\\b.py"):
            with self.subTest(name=name):
                self.make([(name, "pass\n")])
                with self.assertRaises(ValueError):
                    inventory([self.archive])

    def test_duplicate_names_rejected(self):
        self.make([("A.py", "pass"), ("a.py", "pass")])
        with self.assertRaises(ValueError):
            inventory([self.archive])

    def test_private_names_excluded(self):
        self.make([(".env", "SECRET=redacted"), ("tokens.json", "{}"), ("safe.py", "x=1")])
        names = [x["member_path"] for x in inventory([self.archive])["members"]]
        self.assertEqual(names, ["safe.py"])

    def test_sensitive_content_quarantined_not_exported(self):
        secret = "-----BEGIN PRIVATE KEY-----\nsynthetic\n"
        self.make([("safe.py", secret)])
        m = inventory([self.archive])
        self.assertTrue(m["members"][0]["sensitive_pattern_detected"])
        self.assertNotIn(secret, str(m))
        with self.assertRaises(ValueError):
            recover(self.archive, "safe.py", self.dest)

    def test_invalid_python_syntax_never_called_complete(self):
        self.make([("bad.py", "def broken(:\n")])
        self.assertEqual(inventory([self.archive])["members"][0]["python_syntax"], "parse_failed")
        with self.assertRaises(SyntaxError):
            recover(self.archive, "bad.py", self.dest)

    def test_apply_extracts_one_file_with_no_overwrite(self):
        self.make([("tools/one.py", "x=42\n"), ("tools/two.py", "y=2\n")])
        result = recover(self.archive, "tools/one.py", self.dest)
        self.assertEqual(result["status"], "QUARANTINED_NOT_QUALIFIED")
        files = list(self.dest.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), "x=42\n")
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            recover(self.archive, "tools/one.py", self.dest)

    def test_symlink_archive_and_quarantine_rejected(self):
        self.make([("safe.py", "x=1\n")])
        link = self.root / "link.zip"
        link.symlink_to(self.archive)
        with self.assertRaises(ValueError):
            inventory([link])
        target = self.root / "linkdir"
        target.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaises(ValueError):
            recover(self.archive, "safe.py", target)

    def test_oversize_and_high_ratio(self):
        self.make([("bomb.py", "x" * (2 * 1024 * 1024 + 1))])
        with self.assertRaises(ValueError):
            inventory([self.archive])
        with self.assertRaises(ValueError):
            recover(self.archive, "bomb.py", self.dest)

    def test_nonzip_fails(self):
        self.archive.write_text("not a zip")
        with self.assertRaises(zipfile.BadZipFile):
            inventory([self.archive])


if __name__ == "__main__":
    unittest.main()
