"""Offline safety contracts for the live use-case installer (no Debian access)."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/ops/install_live_usecase_12min.py"

class LiveUsecaseInstallerSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_no_crontab_invocation_or_managed_cron_write(self):
        self.assertNotIn('["crontab"', self.source)
        self.assertNotIn('subprocess.run(["crontab"', self.source)
        self.assertNotIn('crontab install', self.source)

    def test_cron_is_explicitly_skipped(self):
        self.assertIn('status="SKIPPED"', self.source)
        self.assertIn('"cron":status', self.source)

    def test_hold_propagates_exit_two(self):
        self.assertIn('return 0 if probe.returncode == 0 else (2 if probe.returncode == 2 else 1)', self.source)

    def test_source_is_immutable_commit_pinned(self):
        self.assertIn('re.fullmatch(r"[a-fA-F0-9]{40}",a.commit)', self.source)
        self.assertIn('fetch_pinned(a.commit.lower())', self.source)

if __name__ == "__main__":
    unittest.main()
