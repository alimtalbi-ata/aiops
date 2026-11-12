"""Negative contract tests: malformed Docker count envelopes never promote OBSERVED."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[2] / "scripts/observability/debian_rootless_readonly.py"
spec = importlib.util.spec_from_file_location("debian_observe", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MalformedCount(unittest.TestCase):
    def test_invalid_counts_fail_closed(self):
        for count in (None, -1, True, 1.0, "1", [], {}):
            with self.subTest(count=count):
                result = module.inventory({"state": "OBSERVED", "value": "a"},
                                          {"state": "OBSERVED", "count": count})
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertEqual(result["reason"], "INVENTORY_COUNT_INVALID")
                self.assertFalse(result["complete"])
                self.assertEqual(result["items"], [])

    def test_missing_count_fails_closed(self):
        result = module.inventory({"state": "OBSERVED", "value": "a"},
                                  {"state": "OBSERVED"})
        self.assertEqual(result["reason"], "INVENTORY_COUNT_INVALID")

    def test_invalid_payload_fails_closed(self):
        result = module.inventory({"state": "OBSERVED", "value": ["a"]},
                                  {"state": "OBSERVED", "count": 1})
        self.assertEqual(result["state"], "UNKNOWN")

    def test_equal_integer_count_still_observed(self):
        result = module.inventory({"state": "OBSERVED", "value": "a"},
                                  {"state": "OBSERVED", "count": 1})
        self.assertEqual(result["state"], "OBSERVED")
        self.assertTrue(result["complete"])

if __name__ == "__main__":
    unittest.main()
