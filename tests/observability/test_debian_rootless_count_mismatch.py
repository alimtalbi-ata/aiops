"""Isolated negative tests for Docker inventory count equality; no host calls."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("debian_observe", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CountMismatch(unittest.TestCase):
    def test_count_smaller_than_listing_is_unknown(self):
        result = module.inventory({"state": "OBSERVED", "value": "a\nb"}, {"state": "OBSERVED", "count": 1})
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "INVENTORY_COUNT_MISMATCH")
        self.assertFalse(result["complete"])

    def test_count_larger_than_listing_is_unknown(self):
        result = module.inventory({"state": "OBSERVED", "value": "a"}, {"state": "OBSERVED", "count": 2})
        self.assertEqual(result["reason"], "INVENTORY_TRUNCATED")
        self.assertFalse(result["complete"])

    def test_equal_count_is_observed(self):
        result = module.inventory({"state": "OBSERVED", "value": "a\nb"}, {"state": "OBSERVED", "count": 2})
        self.assertTrue(result["complete"])

    def test_unverified_count_never_observed(self):
        result = module.inventory({"state": "OBSERVED", "value": "a"}, {"state": "UNKNOWN"})
        self.assertEqual(result["state"], "UNKNOWN")

if __name__ == "__main__":
    unittest.main()
