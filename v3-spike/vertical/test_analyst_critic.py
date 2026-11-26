import unittest
from analyst_critic import analyze, critique

class AnalystCriticTest(unittest.TestCase):
    def test_evidence(self):
        c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        a=analyze(c)
        self.assertTrue(critique(a,c)["evidence_supported"])
        self.assertFalse(critique(a,c)["causality_established"])
        a["evidence_ids"]=["invented"]
        self.assertFalse(critique(a,c)["evidence_supported"])
    def test_unsupported_conclusions(self):
        c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        for mutation in ({"root_cause":"invented","confidence":1}, {"hypothesis":"invented"}, {"confidence":0.9}, {"production_authorized":True}):
            with self.subTest(mutation=mutation):
                a=analyze(c)
                a.update(mutation)
                result=critique(a,c)
                self.assertFalse(result["evidence_supported"])
                self.assertEqual(result["root_cause"],"UNKNOWN")
                self.assertIsNone(result["confidence"])
                self.assertEqual(result["operational_decision"],"DENY")
                self.assertIs(result["production_authorized"],False)
    def test_invalid_references_fail_closed(self):
        valid={"evidence_id":"E1","payload_hash":"a"*64}
        for refs in ([dict(valid,evidence_id="")],[dict(valid,evidence_id=None)],
                     [dict(valid,evidence_id=" ")],[dict(valid,evidence_id=1)],
                     [dict(valid,payload_hash="bad")],[{"evidence_id":"E1"}],
                     [valid,valid],[valid,dict(valid,payload_hash="b"*64)]):
            with self.subTest(refs=refs):
                c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":refs}
                with self.assertRaises(ValueError): analyze(c)
                with self.assertRaises(ValueError): critique({},c)
    def test_empty(self):
        c={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"evidence":[]}
        self.assertEqual(analyze(c)["hypothesis"],"UNKNOWN")
        self.assertFalse(critique(analyze(c),c)["evidence_supported"])
    def test_live(self):
        with self.assertRaises(ValueError):
            analyze({"production_authorized":True})

if __name__=="__main__": unittest.main()
