"""Negative tests for output directory ancestor symlinks (synthetic only)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("debian_rootless_path_guard", SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class OutputPathGuardTests(unittest.TestCase):
    def test_parent_symlink_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "real"
            real.mkdir()
            (root / "alias").symlink_to(real, target_is_directory=True)
            self.assertTrue(collector.has_symlink_ancestor(root / "alias" / "output"))
            self.assertFalse(collector.has_symlink_ancestor(real / "output"))

    def test_main_refuses_symlink_parent_without_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / "real"
            real.mkdir()
            (root / "alias").symlink_to(real, target_is_directory=True)
            with mock.patch.object(collector, "BASE", root / "alias" / "output"), mock.patch.object(
                collector.os, "getuid", return_value=1001
            ):
                self.assertEqual(collector.main(), 3)
            self.assertFalse((real / "output").exists())


if __name__ == "__main__":
    unittest.main()
