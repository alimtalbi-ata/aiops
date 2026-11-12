"""FS147 functional acceptance refuses missing or cross-run integration evidence."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "check_fs147_functional_e2e.py"
spec = importlib.util.spec_from_file_location("check_fs147_functional_e2e", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def receipt():
    return {"schema": "aiops2-fs147-functional-e2e-v1", "mode": "SIMULATED",
            "run_id": "fs147-run-1", "real_effects_executed": False,
            "glpi_ticket": {"ticket_id": "ticket-845", "correlation_id": "fs147-run-1",
                            "operation": "create", "evidence_ref": "glpi/receipt-845"},
            "stages": {name: {"run_id": "fs147-run-1", "source": "reviewed-artifact",
                              "result": "PASS", "evidence_ref": "receipt/" + name}
                       for name in m.STAGES}}


class FunctionalTests(unittest.TestCase):
    def test_all_stages_consistent_is_receipt_pass_not_release_go(self):
        v = m.evaluate(receipt())
        self.assertEqual(v["result"], "PASS")
        self.assertEqual(v["release_decision"], "HOLD")

    def test_missing_worker_critique_blocks(self):
        x = receipt()
        del x["stages"]["worker_critique"]
        self.assertIn("worker_critique:missing", m.evaluate(x)["failures"])

    def test_cross_run_ticket_blocks(self):
        x = receipt()
        x["stages"]["glpi_ticket"]["run_id"] = "other-run"
        self.assertIn("glpi_ticket:run_id_mismatch", m.evaluate(x)["failures"])

    def test_missing_policy_evidence_blocks(self):
        x = receipt()
        x["stages"]["policy_decision"]["evidence_ref"] = ""
        self.assertIn("policy_decision:missing_evidence_ref", m.evaluate(x)["failures"])

    def test_real_effects_block(self):
        x = receipt()
        x["real_effects_executed"] = True
        self.assertIn("real_effects_must_be_false", m.evaluate(x)["failures"])

    def test_unproven_safe_resume_blocks(self):
        x = receipt()
        x["stages"]["safe_resume"]["result"] = "UNKNOWN"
        self.assertIn("safe_resume:not_pass", m.evaluate(x)["failures"])

    def test_wrong_mode_rejected(self):
        x = receipt()
        x["mode"] = "LIVE"
        with self.assertRaisesRegex(ValueError, "SIMULATED"):
            m.evaluate(x)

    def test_any_ticket_identity_is_accepted(self):
        x = receipt()
        x["glpi_ticket"]["ticket_id"] = "ticket-90001"
        self.assertEqual(m.evaluate(x)["result"], "PASS")

    def test_ticket_run_correlation_blocks(self):
        x = receipt()
        x["glpi_ticket"]["correlation_id"] = "unrelated-run"
        self.assertIn("glpi_ticket:correlation_mismatch", m.evaluate(x)["failures"])

    def test_missing_ticket_identity_blocks(self):
        x = receipt()
        x["glpi_ticket"]["ticket_id"] = ""
        self.assertIn("glpi_ticket:missing_ticket_id", m.evaluate(x)["failures"])


if __name__ == "__main__":
    unittest.main()
