"""Nested execution-mode contradictions cannot authorize read-only FS147 stages."""
import unittest
from worker.fs147_readonly_pipeline import _claims_side_effect

class NestedExecutionTests(unittest.TestCase):
    def test_nested_live_or_ambiguous_execution_denied(self):
        for payload in (
            {"metadata": {"dry_run": False}},
            {"metadata": {"dry_run": None}},
            {"metadata": {"dry_run": "true"}},
            {"metadata": {"execution_mode": "LIVE"}},
            {"metadata": {"execution_mode": None}},
            {"audit": [{"dry_run": False}]},
            {"audit": [{"execution_mode": "EXECUTE"}]},
        ):
            with self.subTest(payload=payload):
                self.assertTrue(_claims_side_effect(payload))

    def test_explicit_readonly_metadata_remains_valid(self):
        for payload in (
            {"metadata": {"dry_run": True}},
            {"metadata": {"execution_mode": "SIMULATE"}},
            {"audit": [{"dry_run": True, "execution_mode": "SIMULATE"}]},
        ):
            with self.subTest(payload=payload):
                self.assertFalse(_claims_side_effect(payload))

if __name__ == "__main__":
    unittest.main()
