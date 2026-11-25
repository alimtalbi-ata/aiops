import unittest
from hitl_demo import ApprovalGate

class HITLTest(unittest.TestCase):
    def test_bound_one_use(self):
        g=ApprovalGate()
        k=g.request("i","r",["e"])["request_id"]
        self.assertEqual(g.decide(k,"i","r",["e"],True)["decision"],"SIMULATE_ONLY")
        self.assertEqual(g.decide(k,"i","r",["e"],True)["decision"],"DENY")
    def test_changed_context_and_refusal(self):
        for evidence,approved in [(["other"],True),(["e"],False)]:
            g=ApprovalGate()
            k=g.request("i","r",["e"])["request_id"]
            result=g.decide(k,"i","r",evidence,approved)
            self.assertEqual(result["decision"],"DENY")
            self.assertFalse(result["executed_on_host"])
