"""Regression tests for live Core's wrapped /api/runs/{rid} response."""
import unittest
from unittest.mock import patch
from ops.coordination.core_case_collector import collect


RID = "RUN-8CA56A39E58944F1"
INCIDENT = "INC-FS1250-AUTOGLPI-625916362ACD42C9"


class CoreCaseCollectorTests(unittest.TestCase):
    def test_wrapped_blocked_run_is_observed_without_execution(self):
        def fake_get(base_url, path, token=None, timeout=5):
            if path.endswith("/evidence"):
                return {"items": []}
            return {"run": {"run_id": RID, "incident_id": INCIDENT, "status": "BLOCKED"},
                    "events": [], "gates": [], "stages": []}
        with patch("ops.coordination.core_case_collector._get_json", side_effect=fake_get) as get:
            result = collect(RID)
        self.assertEqual(result["checks"], {"core_run": "PASS", "evidence_api": "PASS"})
        self.assertEqual(result["incident_id"], INCIDENT)
        self.assertEqual(result["run_status"], "BLOCKED")
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("POLICY_BLOCKED_NO_EXECUTION", result["reason_codes"])
        self.assertFalse(result["glpi_link_verified"])
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all("/execute" not in c.args[1] for c in get.call_args_list))

    def test_direct_run_response_is_supported(self):
        with patch("ops.coordination.core_case_collector._get_json", side_effect=[
            {"run_id": RID, "incident_id": INCIDENT, "status": "BLOCKED"}, []
        ]):
            result = collect(RID)
        self.assertEqual(result["checks"]["core_run"], "PASS")

    def test_wrong_run_id_is_rejected(self):
        with patch("ops.coordination.core_case_collector._get_json", return_value={
            "run": {"run_id": "RUN-OTHER", "incident_id": INCIDENT, "status": "BLOCKED"}
        }):
            result = collect(RID)
        self.assertEqual(result["checks"]["core_run"], "HOLD")
        self.assertIn("CORE_RUN_READ_FAILED", result["reason_codes"])

    def test_invalid_nested_record_is_rejected(self):
        with patch("ops.coordination.core_case_collector._get_json", return_value={"run": []}):
            result = collect(RID)
        self.assertEqual(result["checks"]["core_run"], "HOLD")


if __name__ == "__main__":
    unittest.main()
