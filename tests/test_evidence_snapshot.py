"""Offline snapshot pinning regression tests: never contact real applications."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo.evidence_snapshot import pin_captures


class EvidenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.stage = self.root / "stage"
        self.source.mkdir()
        self.stage.mkdir(mode=0o700)
        (self.source / "portal.png").write_bytes(b"P" * 64)

    def pin(self, entries=None):
        return pin_captures(self.source, self.stage,
                            [{"file": "portal.png"}] if entries is None else entries)

    def test_pinned_bytes_survive_source_mutation(self):
        target = self.pin()
        (self.source / "portal.png").write_bytes(b"X" * 64)
        self.assertEqual((target / "portal.png").read_bytes(), b"P" * 64)
        self.assertEqual((target / "portal.png").stat().st_mode & 0o077, 0)
        self.assertEqual(target.stat().st_mode & 0o077, 0)

    def test_symlinked_capture_rejected(self):
        (self.source / "portal.png").unlink()
        (self.source / "portal.png").symlink_to(self.root / "outside")
        (self.root / "outside").write_bytes(b"S" * 64)
        with self.assertRaises(OSError):
            self.pin()

    def test_symlinked_source_root_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "real directory"):
            pin_captures(link, self.stage, [{"file": "portal.png"}])

    def test_path_traversal_and_duplicate_rejected(self):
        for name in ("../secret.png", "/tmp/secret.png", "..\\secret.png"):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(dir=self.root) as td:
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        pin_captures(self.source, Path(td), [{"file": name}])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.pin([{"file": "portal.png"}, {"file": "portal.png"}])

    def test_short_and_oversized_capture_rejected(self):
        (self.source / "portal.png").write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "bounded regular"):
            self.pin()
        (self.source / "portal.png").write_bytes(b"x" * (20 * 1024 * 1024 + 1))
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            with self.assertRaisesRegex(ValueError, "bounded regular"):
                pin_captures(self.source, Path(td), [{"file": "portal.png"}])

    def test_missing_nofollow_fails_closed(self):
        with patch.object(os, "O_NOFOLLOW", 0, create=True):
            with self.assertRaisesRegex(ValueError, "O_NOFOLLOW"):
                self.pin()

    def test_no_overwrite_of_existing_snapshot(self):
        self.pin()
        with self.assertRaises(FileExistsError):
            self.pin()


if __name__ == "__main__":
    unittest.main()
