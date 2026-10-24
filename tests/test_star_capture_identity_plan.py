import unittest
from demo.star_capture_identity_plan import plan_capture_identity

class CaptureIdentityPlanTests(unittest.TestCase):
    def test_missing_all_identifiers_blocks_capture_attempts(self):
        plan=plan_capture_identity("RUN-123")
        self.assertEqual(len(plan["steps"]),9)
        self.assertEqual(plan["capture_attempt_ready_count"],0)
        self.assertEqual(plan["runtime_proof_count"],0)
        self.assertTrue(all(not s["capture_ready_for_attempt"] for s in plan["steps"]))
    def test_identifiers_only_enable_attempt_not_proof(self):
        p=plan_capture_identity("RUN-123",{"alert_id":"ALT-1","execution_by_cue":{"correlate":"EXE-2","enrich":"EXE-3","analyze":"EXE-4","simulate":"EXE-5"},"ticket_id":"TKT-3","approval_id":"APR-4"})
        self.assertEqual(p["capture_attempt_ready_count"],9)
        self.assertEqual(p["runtime_proof_count"],0)
        self.assertTrue(all(not s["authenticated_runtime_proof"] for s in p["steps"]))
    def test_missing_approval_only_blocks_approve(self):
        p=plan_capture_identity("RUN-123",{"alert_id":"ALT-1","execution_by_cue":{"correlate":"EXE-2","enrich":"EXE-3","analyze":"EXE-4","simulate":"EXE-5"},"ticket_id":"TKT-3"})
        self.assertEqual([s["cue"] for s in p["steps"] if not s["capture_ready_for_attempt"]],["approve"])
    def test_shared_execution_id_must_be_rejected(self):
        with self.assertRaises(ValueError):
            plan_capture_identity("RUN-123",{"execution_id":"EXE-SHARED"})
    def test_per_cue_execution_identity_is_preserved(self):
        p=plan_capture_identity("RUN-123",{"execution_by_cue":{"correlate":"EXE-101","enrich":"EXE-102"}})
        self.assertEqual(p["steps"][1]["supplied_identifiers"]["execution_id"],"EXE-101")
        self.assertEqual(p["steps"][2]["supplied_identifiers"]["execution_id"],"EXE-102")
        self.assertFalse(p["steps"][3]["capture_ready_for_attempt"])
    def test_invalid_identities_fail_closed(self):
        for known in ({"ticket_id":"../bad"},{"password":"secret"},{"alert_id":True}):
            with self.subTest(known=known),self.assertRaises(ValueError):
                plan_capture_identity("RUN-123",known)
if __name__=="__main__":unittest.main()
