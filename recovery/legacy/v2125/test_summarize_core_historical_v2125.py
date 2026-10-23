import unittest
from summarize_core_historical_v2125 import summarize

def sample():
    return (
        {'run':{'run_id':'RUN-A4449145A6E377FF','status':'BLOCKED','mode':'DEMO'},'events':[{'evidence_ids':['E1']}], 'stages':[{}]},
        {'run_id':'RUN-A4449145A6E377FF','analyses':[{'evidence_ids':['E1']}],'critiques':[{'evidence_ids':['E1'],'validated':False}], 'policy_decisions':[{'state':'BLOCKED'}]},
        {'run_id':'RUN-A4449145A6E377FF','items':[{'evidence_id':'E1'}]}
    )
class Tests(unittest.TestCase):
    def test_summary(self):
        r=summarize(*sample())
        self.assertEqual(r['critic_validation_declarations'], {'FALSE':1})
        self.assertEqual(r['analyst_evidence']['found_in_export'],1)
        self.assertFalse(r['dgx_independently_attested'])
    def test_mismatch(self):
        a,b,c=sample(); c['run_id']='WRONG'
        with self.assertRaises(ValueError): summarize(a,b,c)
    def test_missing_reference(self):
        a,b,c=sample(); b['analyses'][0]['evidence_ids']=['MISSING']
        self.assertEqual(summarize(a,b,c)['analyst_evidence']['missing_from_export'],1)
    def test_duplicate_evidence(self):
        a,b,c=sample(); c['items'].append({'evidence_id':'E1'})
        with self.assertRaises(ValueError): summarize(a,b,c)
if __name__=='__main__':unittest.main()
