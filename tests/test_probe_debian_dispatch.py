"""Tests for read-only dispatch discovery, without a Debian dependency."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "coordination"))
from probe_debian_dispatch import evaluate

class DiscoveryTests(unittest.TestCase):
    def test_patterns_do_not_prove_dispatch(self):
        result = evaluate({"cron.txt": "* * * * * /home/aiops/poll.sh\n"})
        self.assertEqual(result["status"], "DISPATCH_NOT_VERIFIED")
        self.assertTrue(result["signals"]["poller"])
        self.assertFalse(result["signals"]["codex"])

    def test_secret_lines_never_echo(self):
        result = evaluate({"cron.txt": "token=ghp_secretvalue codex exec\n"})
        self.assertFalse(result["signals"]["codex"])
        self.assertNotIn("ghp_secretvalue", str(result))

    def test_empty_snapshot_not_success(self):
        result = evaluate({"cron.txt": ""})
        self.assertEqual(result["status"], "DISPATCH_NOT_VERIFIED")

    def test_oversize_rejected(self):
        with self.assertRaises(ValueError):
            evaluate({"cron.txt": "a" * 262145})

if __name__ == "__main__":
    unittest.main()
