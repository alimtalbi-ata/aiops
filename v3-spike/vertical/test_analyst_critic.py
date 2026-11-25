import unittest
from analyst_critic import analyze, critique

class AnalystCriticTest(unittest.TestCase):
    def test_evidence(self):
        c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":[{"evidence_id":"E1"}]}
        a=analyze(c)
        self.assertTrue(critique(a,c)["evidence_supported"])
        self.assertFalse(critique(a,c)["causality_established"])
        a["evidence_ids"]=["invented"]
        self.assertFalse(critique(a,c)["evidence_supported"])
    def test_empty(self):
        c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":[]}
        self.assertEqual(analyze(c)["hypothesis"],"UNKNOWN")
        self.assertFalse(critique(analyze(c),c)["evidence_supported"])
    def test_live(self):
        with self.assertRaises(ValueError):
            analyze({"production_authorized":True})

if __name__=="__main__": unittest.main()
