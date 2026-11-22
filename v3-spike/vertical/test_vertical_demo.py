import copy
import unittest
from vertical_demo import execute

EVENT = {"id": "synthetic-001", "source": "synthetic-monitor", "severity": "critical", "resource": "demo-node-01"}

class VerticalTests(unittest.TestCase):
    def test_denied_default(self):
        out = execute(EVENT)
        self.assertEqual(out["policy"]["decision"], "DENY")
        self.assertEqual(out["run"]["status"], "blocked")
        self.assertFalse(out["production_authorized"])
        self.assertEqual(out["gamma"]["receipt"], out["receipt"])

    def test_approved_only_simulates(self):
        out = execute(EVENT, approved=True)
        self.assertEqual(out["policy"]["decision"], "SIMULATE_ONLY")
        self.assertEqual(out["run"]["status"], "simulated")
        self.assertFalse(out["run"]["executed_on_host"])
        self.assertFalse(out["production_authorized"])

    def test_receipt_deterministic(self):
        self.assertEqual(execute(EVENT)["receipt"], execute(copy.deepcopy(EVENT))["receipt"])

    def test_evidence_changes_on_event_mutation(self):
        mutated = {**EVENT, "severity": "warning"}
        self.assertNotEqual(execute(EVENT)["receipt"]["sha256"], execute(mutated)["receipt"]["sha256"])

    def test_invalid_events_fail_closed(self):
        for mutation in ({}, {**EVENT, "id": ""}, {**EVENT, "severity": "low"}, {**EVENT, "resource": None}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                execute(mutation)

if __name__ == "__main__":
    unittest.main()
