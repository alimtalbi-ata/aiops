import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "portal"))
from golden_demo import scenario, journey

class GoldenDemoTests(unittest.TestCase):
    def test_contract_is_synthetic(self):
        contract = scenario()
        self.assertTrue(contract["synthetic"])
        self.assertEqual(contract["mode"], "DEMO")
        self.assertEqual(len(contract["stages"]), 13)

    def test_empty_inventory(self):
        self.assertEqual(journey([])["execution"]["state"], "NOT_STARTED")

    def test_live_run_excluded(self):
        result = journey([{"scenario_id": scenario()["scenario_id"], "mode": "LIVE", "run_id": "live-run"}])
        self.assertIsNone(result["execution"]["run_id"])

    def test_simulation_not_approval(self):
        result = journey([{"scenario_id": scenario()["scenario_id"], "mode": "DEMO", "run_id": "demo-run", "status": "RESOLVED"}])
        self.assertFalse(result["execution"]["human_approval_executed"])
        self.assertFalse(result["execution"]["remediation_executed"])
        self.assertFalse(result["execution"]["evidence_qualified"])

if __name__ == "__main__":
    unittest.main()
