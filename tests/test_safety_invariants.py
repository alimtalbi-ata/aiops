import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from shared.safety import canonical_sha256, critical_approval_complete, gold_set_eligible

class SafetyInvariantTests(unittest.TestCase):
    def test_canonical_hash_ignores_dictionary_insertion_order(self):
        self.assertEqual(canonical_sha256({"a":1,"b":2}), canonical_sha256({"b":2,"a":1}))

    def test_critical_approval_requires_two_distinct_required_roles(self):
        self.assertFalse(critical_approval_complete({"security_admin"}))
        self.assertFalse(critical_approval_complete({"security_admin","storage_admin"}))
        self.assertTrue(critical_approval_complete({"security_admin","incident_commander"}))

    def test_synthetic_cases_never_enter_gold_set(self):
        self.assertFalse(gold_set_eligible("DEMO", False, True, True))
        self.assertFalse(gold_set_eligible("LIVE", True, True, True))
        self.assertFalse(gold_set_eligible("LIVE", False, False, True))
        self.assertFalse(gold_set_eligible("LIVE", False, True, False))
        self.assertTrue(gold_set_eligible("LIVE", False, True, True))

if __name__ == "__main__":
    unittest.main()
