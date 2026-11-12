"""Synthetic fail-closed tests for aggregate-only systemd observation."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("host_observe", MODULE)
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

class SystemdAggregateTests(unittest.TestCase):
    def test_counts_without_exposing_unit_names(self):
        payload = b"secret-customer.service loaded active running confidential\nother.service loaded inactive dead confidential\n"
        with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, payload, b"")):
            result = host.inventory_count(["systemctl", "--user", "list-units"])
        self.assertEqual(result, {"state": "OBSERVED", "count": 2})
        self.assertNotIn("secret-customer", str(result))
        self.assertNotIn("confidential", str(result))

    def test_failed_command_is_unknown(self):
        with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"private")):
            result = host.inventory_count(["systemctl", "--user", "list-units"])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertNotIn("private", str(result))

    def test_timeout_is_unknown(self):
        with patch.object(host.subprocess, "run", side_effect=subprocess.TimeoutExpired(["systemctl"], 5)):
            result = host.inventory_count(["systemctl", "--user", "list-units"])
        self.assertEqual(result["state"], "UNKNOWN")

if __name__ == "__main__":
    unittest.main()
