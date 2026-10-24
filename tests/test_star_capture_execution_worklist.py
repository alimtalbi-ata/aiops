import unittest
from demo.star_capture_identity_plan import plan_capture_identity
from demo.star_legacy_capture_gap_plan import build_gap_plan
from demo.star_capture_execution_worklist import join_capture_plans

def historical():
    return build_gap_plan({"schema": "aiops-legacy-playwright-audit-v1", "entries": []}, "RUN-123")

class JoinCapturePlansTests(unittest.TestCase):
    def test_missing_ids_fail_closed(self):
        work = join_capture_plans(plan_capture_identity("RUN-123"), historical())
        self.assertEqual(work["ready_for_attempt"], 0)
        self.assertEqual(work["runtime_proof_count"], 0)
        self.assertEqual(len(work["steps"]), 9)

    def test_partial_readiness(self):
        plan = plan_capture_identity("RUN-123", {"alert_id":"ALERT-001"})
        work = join_capture_plans(plan, historical())
        self.assertEqual(work["ready_for_attempt"], 2)
        self.assertEqual([s["cue"] for s in work["steps"] if s["status"] == "READY_FOR_READ_ONLY_CAPTURE"], ["detect", "verify"])

    def test_cross_run_mix_rejected(self):
        with self.assertRaisesRegex(ValueError, "run_id mismatch"):
            join_capture_plans(plan_capture_identity("RUN-OTHER"), historical())

    def test_forged_runtime_proof_rejected(self):
        plan = plan_capture_identity("RUN-123")
        plan["steps"][0]["authenticated_runtime_proof"] = True
        with self.assertRaisesRegex(ValueError, "runtime"):
            join_capture_plans(plan, historical())

    def test_forged_readiness_is_rejected(self):
        p = plan_capture_identity("RUN-123")
        p["steps"][0]["capture_ready_for_attempt"] = True
        with self.assertRaisesRegex(ValueError, "forged capture readiness"):
            join_capture_plans(p, historical())

    def test_removed_required_identifier_is_rejected(self):
        p = plan_capture_identity("RUN-123", {"alert_id": "ALT-123"})
        del p["steps"][0]["supplied_identifiers"]["alert_id"]
        with self.assertRaisesRegex(ValueError, "tampered missing identifiers"):
            join_capture_plans(p, historical())

    def test_mismatched_cue_run_is_rejected(self):
        p = plan_capture_identity("RUN-123")
        p["steps"][0]["supplied_identifiers"]["run_id"] = "RUN-OTHER"
        with self.assertRaisesRegex(ValueError, "cue run_id mismatch"):
            join_capture_plans(p, historical())

    def test_misaligned_steps_rejected(self):
        gap = historical()
        gap["steps"][0]["cue"] = "analyze"
        with self.assertRaises(ValueError):
            join_capture_plans(plan_capture_identity("RUN-123"), gap)

if __name__ == "__main__":
    unittest.main()
