"""Negative contract tests; no Docker/systemd/host access."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch
import subprocess

MODULE = pathlib.Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("collector", MODULE)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class InventoryContract(unittest.TestCase):
    def test_complete(self):
        result = collector.inventory({"state": "OBSERVED", "value": "a\nb"}, {"state": "OBSERVED", "count": 2})
        self.assertEqual((result["state"], result["complete"]), ("OBSERVED", True))

    def test_truncated_count_fails_closed(self):
        result = collector.inventory({"state": "OBSERVED", "value": "a\nb"}, {"state": "OBSERVED", "count": 210})
        self.assertEqual((result["state"], result["reason"], result["complete"]),
                         ("UNKNOWN", "INVENTORY_TRUNCATED", False))

    def test_missing_count_fails_closed(self):
        result = collector.inventory({"state": "OBSERVED", "value": "a"}, {"state": "UNKNOWN"})
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["items"], [])

    def test_unavailable_listing_fails_closed(self):
        result = collector.inventory({"state": "UNKNOWN"}, {"state": "OBSERVED", "count": 3})
        self.assertEqual(result["state"], "UNKNOWN")

    def test_limit_fails_closed(self):
        result = collector.inventory({"state": "OBSERVED", "value": "a\nb"}, {"state": "OBSERVED", "count": 2}, limit=1)
        self.assertEqual(result["reason"], "INVENTORY_TRUNCATED")

    @patch.object(collector.subprocess, "run", side_effect=subprocess.TimeoutExpired(["docker"], 5))
    def test_count_timeout(self, run):
        self.assertEqual(collector.inventory_count(["docker", "ps", "-aq"])["state"], "UNKNOWN")

    @patch.object(collector.subprocess, "run")
    def test_count_command_failure(self, run):
        run.return_value.returncode = 1
        self.assertEqual(collector.inventory_count(["docker", "ps", "-aq"])["reason"], "COUNT_FAILED")

if __name__ == "__main__":
    unittest.main()
