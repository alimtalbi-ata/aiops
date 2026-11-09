import unittest
from worker.fs147_stage_handoff import evaluate_handoff

class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.obs = {"status":"ACCEPTED","fingerprint":"a"*64}
        self.base = {"run_id":"run-1","ticket_id":147,"tenant_id":"tenant-1","observation_fingerprint":"a"*64,"status":"PASS","unknown":False}
        self.analyst = dict(self.base,evidence_sufficient=True)
        self.critic = dict(self.base,approved=True)
        self.policy = dict(self.base,allowed_mode="OBSERVE")
    def call(self):
        return evaluate_handoff(self.obs,self.analyst,self.critic,self.policy,run_id="run-1",ticket_id=147,tenant_id="tenant-1")
    def test_read_only_receipt_deterministic(self):
        a=self.call()
        self.assertEqual(a["status"],"READY_FOR_EVIDENCE")
        self.assertFalse(a["dispatch_allowed"])
        self.assertEqual(a,self.call())
    def test_missing_observation(self):
        self.obs={}
        self.assertEqual(self.call()["status"],"UNKNOWN")
    def test_analyst_insufficient(self):
        self.analyst["evidence_sufficient"]=False
        self.assertEqual(self.call()["reason"],"ANALYST_INSUFFICIENT")
    def test_critic_denied(self):
        self.critic["approved"]=False
        self.assertEqual(self.call()["status"],"UNKNOWN")
    def test_policy_denied(self):
        self.policy["allowed_mode"]="LIVE"
        self.assertEqual(self.call()["status"],"UNKNOWN")
    def test_identity_mismatch(self):
        self.critic["run_id"]="other"
        self.assertEqual(self.call()["reason"],"CRITIC_IDENTITY_MISMATCH")
    def test_unknown_is_not_pass(self):
        self.policy["unknown"]=True
        self.assertEqual(self.call()["status"],"UNKNOWN")
    def test_noncanonical(self):
        self.analyst["bad"]=float("nan")
        self.assertEqual(self.call()["reason"],"NONCANONICAL_HANDOFF")
    def test_forged_nonhex_fingerprint_refused(self):
        for value in ("z"*64, "A"*64, " "*64, "a"*63, "a"*65):
            with self.subTest(value=value):
                self.obs["fingerprint"] = value
                receipt = self.call()
                self.assertEqual(receipt["reason"], "OBSERVATION_UNVERIFIED")
                self.assertIsNone(receipt["digest"])
                self.assertFalse(receipt["dispatch_allowed"])
    def test_mismatched_fingerprint_stage_refused(self):
        self.critic["observation_fingerprint"] = "b"*64
        self.assertEqual(self.call()["reason"], "CRITIC_IDENTITY_MISMATCH")
    def test_deeply_nested_analyst_payload_fails_closed(self):
        root = {}
        node = root
        for _ in range(10000):
            child = {}
            node["next"] = child
            node = child
        self.analyst["nested"] = root
        receipt = self.call()
        self.assertEqual(receipt["status"], "UNKNOWN")
        self.assertEqual(receipt["reason"], "NONCANONICAL_HANDOFF")
        self.assertIsNone(receipt["digest"])
        self.assertFalse(receipt["dispatch_allowed"])
if __name__ == "__main__":
    unittest.main()
