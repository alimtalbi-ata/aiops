"""Contract tests for actual run_linkage_gate.py report fields."""
import unittest
from ops.coordination.debian_linkage_adapter import evaluate_linkage

def report():
    checks = {k: "PASS" for k in (
        "core_run", "core_api", "evidence_api", "critic_policy_outbox",
        "glpi_core_link", "itsm_readback", "temporal_worker_execution",
        "hitl_action_binding")}
    return {"schema": "aiops2-run-linkage-gate-v1", "read_only": True,
            "run_id": "RUN-FS1250-TEST", "verdict": "PASS",
            "core": {"run": {"http": 200}},
            "checks": checks,
            "database": {
                "glpi_links": [{"state": "CONFIRMED", "glpi_ticket_id": 201}],
                "itsm_xref": [{"ticket_id": 201, "glpi_ticket_readback_verified": True}]}}

class LinkageContractTests(unittest.TestCase):
    def test_full_linkage_still_requires_independent_attestations(self):
        self.assertEqual(evaluate_linkage(report()), {
            "status": "HOLD", "reasons": ["INDEPENDENT_SOURCE_ATTESTATIONS_REQUIRED"]})

    def test_current_worker_and_hitl_unverified(self):
        r = report()
        r["checks"]["temporal_worker_execution"] = "UNVERIFIED"
        r["checks"]["hitl_action_binding"] = "UNVERIFIED"
        result = evaluate_linkage(r)
        self.assertIn("LINKAGE_TEMPORAL_WORKER_EXECUTION_NOT_PASS", result["reasons"])
        self.assertIn("LINKAGE_HITL_ACTION_BINDING_NOT_PASS", result["reasons"])

    def test_glpi_ticket_mismatch_holds(self):
        r = report()
        r["database"]["itsm_xref"][0]["ticket_id"] = 202
        self.assertIn("GLPI_SAME_TICKET_READBACK_UNVERIFIED",
                      evaluate_linkage(r)["reasons"])

    def test_user_observed_ticket_does_not_count(self):
        r = report()
        r["external_glpi_observation"] = {"ticket_id": 201}
        r["database"]["itsm_xref"] = []
        self.assertIn("GLPI_SAME_TICKET_READBACK_UNVERIFIED",
                      evaluate_linkage(r)["reasons"])

    def test_missing_db_and_invalid_schema_hold(self):
        r = report()
        del r["database"]
        self.assertEqual(evaluate_linkage(r)["status"], "HOLD")
        r = report()
        r["schema"] = "unknown"
        self.assertEqual(evaluate_linkage(r)["reasons"], ["INVALID_LINKAGE_REPORT"])

if __name__ == "__main__":
    unittest.main()
