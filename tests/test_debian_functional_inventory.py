"""Safety/shape regression for manual Debian inventory."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts/ops/debian_functional_inventory.py"
spec = importlib.util.spec_from_file_location("debian_functional_inventory", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InventoryTests(unittest.TestCase):
    def test_no_http_without_opt_in(self):
        with patch.object(m, "lines", return_value={"status": "missing_command", "items": []}), \
             patch.object(m, "command", return_value={"status": "missing_command"}), \
             patch.object(m, "probe") as probe:
            result = m.collect(False)
            probe.assert_not_called()
            self.assertFalse(result["functional"]["http_probe_enabled"])
            self.assertIn("timedatectl", result["clock"])

    def test_http_only_opt_in_and_loopback(self):
        with patch.object(m, "lines", return_value={"status": "ok", "items": []}), \
             patch.object(m, "command", return_value={"status": "ok"}), \
             patch.object(m, "probe", return_value={"status": "unreachable"}) as probe:
            result = m.collect(True)
            self.assertTrue(probe.called)
            self.assertEqual(len(result["functional"]["loopback_http"]), len(m.SAFE_PORTS))

    def test_secret_field_names_not_collected(self):
        self.assertTrue(m.REDACT.search("api_token"))
        self.assertTrue(m.REDACT.search("private_key"))


if __name__ == "__main__":
    unittest.main()
