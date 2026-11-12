"""Fail-closed tests: incomplete inventories must not expose partial identifiers."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("debian_rootless_readonly", SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class UnknownInventoryPrivacyTests(unittest.TestCase):
    def test_truncated_inventory_exposes_no_partial_ids(self):
        result = collector.inventory(
            {"state": "OBSERVED", "value": "sensitive-id-a\nsensitive-id-b"},
            {"state": "OBSERVED", "count": 3}, limit=2)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "INVENTORY_TRUNCATED")
        self.assertEqual(result["items"], [])
        self.assertIs(result["complete"], False)

    def test_count_mismatch_exposes_no_partial_ids(self):
        result = collector.inventory(
            {"state": "OBSERVED", "value": "sensitive-id-a\nsensitive-id-b"},
            {"state": "OBSERVED", "count": 1}, limit=2)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "INVENTORY_COUNT_MISMATCH")
        self.assertEqual(result["items"], [])
        self.assertIs(result["complete"], False)

    def test_complete_inventory_retains_expected_items(self):
        result = collector.inventory(
            {"state": "OBSERVED", "value": "id-a\nid-b"},
            {"state": "OBSERVED", "count": 2}, limit=2)
        self.assertEqual(result["state"], "OBSERVED")
        self.assertEqual(result["items"], ["id-a", "id-b"])
        self.assertIs(result["complete"], True)

if __name__ == "__main__":
    unittest.main()
