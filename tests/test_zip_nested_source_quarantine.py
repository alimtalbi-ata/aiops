"""Offline synthetic qualification of one-level historical ZIP quarantine."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch

from recovery.tools.nested_source_quarantine import quarantine_nested_source, main


class NestedSourceQuarantineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.outer = self.root / "AIOPS-V2.13.6-SYNTHETIC.zip"
        self.quarantine = self.root / "quarantine"
        self.quarantine.mkdir()
        self.nested_path = "backup/hybrid.zip"
        self.source_path = "scripts/handler.py"
        self.source = b"print('synthetic fixture')\n"
        self.build()

    def build(self, *, source=None, source_path=None, nested_path=None, extra=()):
        if source is not None:
            self.source = source
        if source_path is not None:
            self.source_path = source_path
        if nested_path is not None:
            self.nested_path = nested_path
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as inner:
            inner.writestr(self.source_path, self.source)
            for path, value in extra:
                inner.writestr(path, value)
        self.nested = buffer.getvalue()
        with zipfile.ZipFile(self.outer, "w", zipfile.ZIP_DEFLATED) as outer:
            outer.writestr(self.nested_path, self.nested)
            outer.writestr("README.md", "synthetic release\n")

    def call(self, **changes):
        params = {
            "expected_outer_sha256": hashlib.sha256(self.outer.read_bytes()).hexdigest(),
            "expected_nested_sha256": hashlib.sha256(self.nested).hexdigest(),
            "expected_member_sha256": hashlib.sha256(self.source).hexdigest(),
            "quarantine": self.quarantine,
            "apply": False,
        }
        params.update(changes)
        return quarantine_nested_source(self.outer, self.nested_path, self.source_path, **params)

    def test_dry_run_verifies_all_three_hashes_without_writes(self):
        result = self.call()
        self.assertEqual(result["status"], "VALIDATED_DRY_RUN_NOT_IMPORTED")
        self.assertEqual(result["member_sha256"], hashlib.sha256(self.source).hexdigest())
        self.assertFalse(result["import_authorized"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["source_completeness_attested"])
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_explicit_apply_creates_private_file_and_never_overwrites(self):
        result = self.call(apply=True)
        self.assertEqual(result["status"], "QUARANTINED_NOT_QUALIFIED")
        path = self.quarantine / result["quarantine_file"]
        self.assertEqual(path.read_bytes(), self.source)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.call(apply=True)
        self.assertEqual(len(list(self.quarantine.iterdir())), 1)

    def test_all_three_hash_pins_are_independent_and_mandatory(self):
        for field in ("expected_outer_sha256", "expected_nested_sha256", "expected_member_sha256"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.call(**{field: "0" * 64}, apply=True)
        with self.assertRaises(ValueError):
            self.call(expected_member_sha256="A" * 64)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_nested_source_cannot_escape_or_recurse(self):
        for path in ("../escape.py", "/tmp/escape.py", "C:/unsafe.py", "tokens.json",
                     "third.zip", "CON.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                quarantine_nested_source(
                    self.outer, self.nested_path, path,
                    expected_outer_sha256=hashlib.sha256(self.outer.read_bytes()).hexdigest(),
                    expected_nested_sha256=hashlib.sha256(self.nested).hexdigest(),
                    expected_member_sha256=hashlib.sha256(self.source).hexdigest(),
                    quarantine=self.quarantine, apply=True)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_inner_member_traversal_rejected_before_writes(self):
        self.build(source_path="../escape.py")
        with self.assertRaises(ValueError):
            self.call(apply=True)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_sensitive_source_never_quarantined(self):
        self.build(source=b"-----BEGIN PRIVATE KEY-----\nsynthetic\n")
        with self.assertRaises(ValueError):
            self.call(apply=True)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_syntax_error_never_called_complete(self):
        self.build(source=b"def broken(:\n")
        with self.assertRaises(SyntaxError):
            self.call(apply=True)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_nested_compression_bomb_rejected(self):
        self.build(extra=[("oversized.py", b"A" * (2 * 1024 * 1024))])
        with self.assertRaisesRegex(ValueError, "high-ratio|oversized"):
            self.call(apply=True)
        self.assertEqual(list(self.quarantine.iterdir()), [])

    def test_symlink_source_and_quarantine_rejected(self):
        link = self.root / "outer-link.zip"
        link.symlink_to(self.outer)
        with self.assertRaises(ValueError):
            quarantine_nested_source(
                link, self.nested_path, self.source_path,
                expected_outer_sha256=hashlib.sha256(self.outer.read_bytes()).hexdigest(),
                expected_nested_sha256=hashlib.sha256(self.nested).hexdigest(),
                expected_member_sha256=hashlib.sha256(self.source).hexdigest())
        dest_link = self.root / "dest-link"
        dest_link.symlink_to(self.quarantine, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.call(quarantine=dest_link, apply=True)

    def test_cli_dry_run_and_generic_failure_do_not_disclose_source(self):
        args = [
            str(self.outer), "--nested-member", self.nested_path,
            "--source-member", self.source_path,
            "--outer-sha256", hashlib.sha256(self.outer.read_bytes()).hexdigest(),
            "--nested-sha256", hashlib.sha256(self.nested).hexdigest(),
            "--member-sha256", hashlib.sha256(self.source).hexdigest(),
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "VALIDATED_DRY_RUN_NOT_IMPORTED")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args[:-1] + ["0" * 64]), 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "REJECTED")
        self.assertNotIn("synthetic fixture", output.getvalue())
        self.assertEqual(list(self.quarantine.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
