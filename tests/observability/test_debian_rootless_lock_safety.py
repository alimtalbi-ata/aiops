"""Negative tests for collector lockfile trust boundary (no Docker or Debian access)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("debian_rootless_readonly_lock", SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class LockSafetyTests(unittest.TestCase):
    def test_symlink_lock_refused_without_touching_target(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            target = base / "sentinel"
            target.write_text("unchanged")
            (base / ".lock").symlink_to(target)
            with mock.patch.object(collector, "BASE", base), mock.patch.object(
                collector.os, "getuid", return_value=1001
            ), mock.patch.object(collector.Path, "stat", autospec=True) as stat_mock:
                original_stat = Path.stat
                stat_mock.side_effect = lambda p, *a, **kw: (
                    type("S", (), {"st_uid": 1001, "st_mode": 0o40700})()
                    if p == base else original_stat(p, *a, **kw)
                )
                self.assertEqual(collector.main(), 3)
            self.assertEqual(target.read_text(), "unchanged")
            self.assertFalse(list(base.glob("host-*.json")))


if __name__ == "__main__":
    unittest.main()
