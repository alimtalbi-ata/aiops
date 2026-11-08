"""Contract regression for E2E lineage presentation; no network or LIVE calls.

Run: python -m unittest discover -s tests -p 'test_fs_real_stage_contract.py'
"""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "app/portal/fs_real_readiness.py"
spec = importlib.util.spec_from_file_location("fs_real_readiness", MODULE)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class StageContractTests(unittest.TestCase):
    def test_full_pipeline_order_and_fail_closed_mixed_receipts(self):
        self.assertEqual(readiness.REQUIRED, (
            "source", "core", "evidence", "critic", "policy",
            "temporal", "worker", "itsm"))
        stages = {
            "source": {"status": "PASS", "evidence_ref": "event:147"},
            "core": {"status": "PASS", "evidence_ref": "core:147"},
            "evidence": {"status": "PASS", "evidence_ref": "  "},
            "critic": {"status": "FAIL", "evidence_ref": "critic:147"},
            "policy": {"status": "BLOCKED", "evidence_ref": "policy:147"},
            "temporal": {"status": "PASS"},
            "worker": {"status": "NOT_APPLICABLE"},
            "itsm": {"status": "PASS", "evidence_ref": "glpi:201"},
        }
        result = readiness.summarize_lineage({"read_only": True, "stages": stages})
        self.assertEqual(result["verified_pass_count"], 3)
        self.assertEqual(result["coverage_percent"], 38)
        self.assertEqual(result["unqualified_stages"], [
            "evidence", "critic", "policy", "temporal", "worker"])
        self.assertEqual([q["stage"] for q in result["human_questions"]],
                         result["unqualified_stages"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["approval"], "UNVERIFIED")
        self.assertEqual(result["resolution"], "UNVERIFIED")

    def test_malformed_stage_and_unknown_status_never_pass(self):
        result = readiness.summarize_lineage({
            "read_only": True,
            "stages": {"core": "PASS", "policy": {"status": "APPROVED",
                      "evidence_ref": "fake"}, "itsm": {"status": "PASS",
                      "evidence_ref": 201}},
        })
        self.assertEqual(result["verified_pass_count"], 0)
        self.assertEqual(len(result["human_questions"]), 8)
        self.assertEqual(result["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
