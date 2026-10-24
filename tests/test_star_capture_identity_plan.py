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
        p=plan_capture_identity("RUN-123",{"alert_id":"ALT-1","execution_id":"EXE-2","ticket_id":"TKT-3","approval_id":"APR-4"})
        self.assertEqual(p["capture_attempt_ready_count"],9)
        self.assertEqual(p["runtime_proof_count"],0)
        self.assertTrue(all(not s["authenticated_runtime_proof"] for s in p["steps"]))
    def test_missing_approval_only_blocks_approve(self):
        p=plan_capture_identity("RUN-123",{"alert_id":"ALT-1","execution_id":"EXE-2","ticket_id":"TKT-3"})
        self.assertEqual([s["cue"] for s in p["steps"] if not s["capture_ready_for_attempt"]],["approve"])
    def test_invalid_identities_fail_closed(self):
        for known in ({"ticket_id":"../bad"},{"password":"secret"},{"alert_id":True}):
            with self.subTest(known=known),self.assertRaises(ValueError):
                plan_capture_identity("RUN-123",known)
if __name__=="__main__":unittest.main()
