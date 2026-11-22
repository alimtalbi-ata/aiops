import copy
import unittest
from vertical_demo import execute, verify_projection

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

    def test_nonboolean_approval_denied(self):
        for value in ("false", 1, None, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                execute(EVENT, approved=value)

    def test_incident_scoped_by_tenant_and_resource(self):
        base = execute(EVENT)["incident"]["id"]
        self.assertNotEqual(base, execute({**EVENT, "tenant": "other"})["incident"]["id"])
        self.assertNotEqual(base, execute({**EVENT, "resource": "other"})["incident"]["id"])

    def test_projection_tamper_rejected(self):
        output = execute(EVENT, approved=True)
        self.assertTrue(verify_projection(output))
        for field in ("policy", "receipt", "gamma"):
            tampered = copy.deepcopy(output)
            if field == "policy":
                tampered["policy"]["decision"] = "DENY"
            elif field == "receipt":
                tampered["receipt"]["sha256"] = "0" * 64
            else:
                tampered["gamma"]["receipt"]["policy"] = "DENY"
            with self.subTest(field=field):
                self.assertFalse(verify_projection(tampered))

    def test_invalid_events_fail_closed(self):
        for mutation in ({}, {**EVENT, "id": ""}, {**EVENT, "severity": "low"}, {**EVENT, "resource": None}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                execute(mutation)

if __name__ == "__main__":
    unittest.main()
