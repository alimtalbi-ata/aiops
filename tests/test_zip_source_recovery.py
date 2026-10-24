"""Isolated, synthetic ZIP fixtures: no prod services, ports or private data."""
import hashlib
import os
import sys
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest
import zipfile
from recovery.tools.zip_source_recovery import inventory, recover, main


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

    def pinned(self, member, *, archive=None, destination=None, archive_pin=None, member_pin=None):
        source = archive or self.archive
        with zipfile.ZipFile(source) as z:
            content = z.read(member)
        return recover(source, member, destination or self.dest,
                       expected_archive_sha256=archive_pin or hashlib.sha256(source.read_bytes()).hexdigest(),
                       expected_member_sha256=member_pin or hashlib.sha256(content).hexdigest())

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
            self.pinned("safe.py")

    def test_invalid_python_syntax_never_called_complete(self):
        self.make([("bad.py", "def broken(:\n")])
        self.assertEqual(inventory([self.archive])["members"][0]["python_syntax"], "parse_failed")
        with self.assertRaises(SyntaxError):
            self.pinned("bad.py")

    def test_apply_extracts_one_file_with_no_overwrite(self):
        self.make([("tools/one.py", "x=42\n"), ("tools/two.py", "y=2\n")])
        result = self.pinned("tools/one.py")
        self.assertEqual(result["status"], "QUARANTINED_NOT_QUALIFIED")
        files = list(self.dest.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), "x=42\n")
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.pinned("tools/one.py")

    def test_symlink_archive_and_quarantine_rejected(self):
        self.make([("safe.py", "x=1\n")])
        link = self.root / "link.zip"
        link.symlink_to(self.archive)
        with self.assertRaises(ValueError):
            inventory([link])
        target = self.root / "linkdir"
        target.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.pinned("safe.py", destination=target)

    def test_oversize_and_high_ratio(self):
        self.make([("bomb.py", "x" * (2 * 1024 * 1024 + 1))])
        with self.assertRaises(ValueError):
            inventory([self.archive])
        with self.assertRaises(ValueError):
            self.pinned("bomb.py")

    def test_missing_pins_refused(self):
        self.make([("safe.py", "x=1\n")])
        with self.assertRaises(TypeError):
            recover(self.archive, "safe.py", self.dest)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_archive_changed_after_review_fails_closed(self):
        self.make([("safe.py", "x=1\n")])
        original = inventory([self.archive])["members"][0]
        self.make([("safe.py", "x=2\n")])
        with self.assertRaisesRegex(ValueError, "archive SHA-256"):
            self.pinned("safe.py", archive_pin=original["archive_sha256"],
                        member_pin=original["member_sha256"])
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_wrong_member_pin_fails_closed(self):
        self.make([("safe.py", "x=1\n")])
        with self.assertRaisesRegex(ValueError, "member bytes"):
            self.pinned("safe.py", member_pin="0" * 64)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_extraction_rejects_unrelated_unsafe_archive_member(self):
        self.make([("safe.py", "x=1\n"), ("../outside.py", "x=2\n")])
        with self.assertRaisesRegex(ValueError, "unsafe ZIP member path"):
            self.pinned("safe.py")
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_extraction_rejects_duplicate_casefold_names(self):
        self.make([("safe.py", "x=1\n"), ("SAFE.py", "x=2\n")])
        with self.assertRaisesRegex(ValueError, "duplicate ZIP member path"):
            self.pinned("safe.py")
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_extraction_rejects_oversized_unrelated_member(self):
        self.make([("safe.py", "x=1\n"), ("huge.py", "x" * (2 * 1024 * 1024 + 1))])
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.pinned("safe.py")
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_cli_requires_both_reviewed_pins(self):
        self.make([("safe.py", "x=1\n")])
        args = ["zip_source_recovery", str(self.archive), "--apply", "--allow", "safe.py",
                "--quarantine", str(self.dest)]
        with patch.object(sys, "argv", args), self.assertRaises(SystemExit) as caught:
            main()
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_cli_pinned_quarantine(self):
        self.make([("safe.py", "x=1\n")])
        row = inventory([self.archive])["members"][0]
        args = ["zip_source_recovery", str(self.archive), "--apply", "--allow", "safe.py",
                "--quarantine", str(self.dest), "--expected-archive-sha256", row["archive_sha256"],
                "--expected-member-sha256", row["member_sha256"]]
        with patch.object(sys, "argv", args):
            main()
        self.assertEqual(len(list(self.dest.iterdir())), 1)

    def test_inventory_uses_same_descriptor_after_path_replacement(self):
        """A rename between SHA calculation and ZIP parsing cannot rebind bytes."""
        self.make([("safe.py", "x=1\n")])
        original_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        real_zipfile = zipfile.ZipFile
        moved = self.root / "reviewed-original.zip"
        replaced = []

        def swap_then_parse(source, *args, **kwargs):
            if not replaced:
                self.archive.rename(moved)
                with real_zipfile(self.archive, "w") as replacement:
                    replacement.writestr("safe.py", "x=999\n")
                replaced.append(True)
            return real_zipfile(source, *args, **kwargs)

        with patch("recovery.tools.zip_source_recovery.zipfile.ZipFile", side_effect=swap_then_parse):
            report = inventory([self.archive])
        self.assertTrue(replaced)
        self.assertEqual(report["members"][0]["archive_sha256"], original_hash)
        self.assertEqual(report["members"][0]["member_sha256"], hashlib.sha256(b"x=1\n").hexdigest())
        self.assertNotEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(), original_hash)

    def test_recover_pinned_descriptor_survives_path_replacement(self):
        """Selected bytes and whole-ZIP validation stay on the hashed descriptor."""
        self.make([("safe.py", "x=1\n")])
        archive_pin = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        member_pin = hashlib.sha256(b"x=1\n").hexdigest()
        real_zipfile = zipfile.ZipFile
        moved = self.root / "reviewed-original.zip"
        replaced = []

        def swap_then_parse(source, *args, **kwargs):
            if not replaced:
                self.archive.rename(moved)
                with real_zipfile(self.archive, "w") as replacement:
                    replacement.writestr("safe.py", "x=999\n")
                replaced.append(True)
            return real_zipfile(source, *args, **kwargs)

        with patch("recovery.tools.zip_source_recovery.zipfile.ZipFile", side_effect=swap_then_parse):
            result = recover(self.archive, "safe.py", self.dest,
                             expected_archive_sha256=archive_pin,
                             expected_member_sha256=member_pin)
        self.assertEqual(result["status"], "QUARANTINED_NOT_QUALIFIED")
        self.assertEqual(next(self.dest.iterdir()).read_bytes(), b"x=1\n")
        self.assertNotEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(), archive_pin)

    def test_symlink_swap_at_open_refused(self):
        """O_NOFOLLOW protects even if is_symlink preflight was bypassed."""
        self.make([("safe.py", "x=1\n")])
        original = self.root / "reviewed-original.zip"
        self.archive.rename(original)
        self.archive.symlink_to(original)
        with patch.object(Path, "is_symlink", return_value=False), patch.object(Path, "is_file", return_value=True):
            with self.assertRaises(OSError):
                inventory([self.archive])
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_nonzip_fails(self):
        self.archive.write_text("not a zip")
        with self.assertRaises(zipfile.BadZipFile):
            inventory([self.archive])


if __name__ == "__main__":
    unittest.main()
