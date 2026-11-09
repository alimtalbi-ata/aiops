"""Offline smoke tests for the pure Codex dispatch command parser."""

import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))

from dispatch_codex_once import parse_command


class CodexPilotSmokeTests(unittest.TestCase):
    SHA = "0123456789abcdef0123456789abcdef01234567"
    NOW = dt.datetime(2026, 11, 9, 10, 0, 0, tzinfo=dt.timezone.utc)

    def test_accepts_future_utc_command_with_exact_sha(self):
        command = f"AIOPS2_CODEX_DISPATCH_V1 {self.SHA} 2026-11-09T11:00:00Z"
        self.assertEqual(parse_command(command, self.NOW, self.SHA), self.SHA)

    def test_rejects_expired_command(self):
        command = f"AIOPS2_CODEX_DISPATCH_V1 {self.SHA} 2026-11-09T09:59:59Z"
        with self.assertRaisesRegex(ValueError, "expired or excessive TTL"):
            parse_command(command, self.NOW, self.SHA)

    def test_rejects_mismatched_sha(self):
        command = f"AIOPS2_CODEX_DISPATCH_V1 {'a' * 40} 2026-11-09T11:00:00Z"
        with self.assertRaisesRegex(ValueError, "unexpected exact source SHA"):
            parse_command(command, self.NOW, self.SHA)


if __name__ == "__main__":
    unittest.main()
