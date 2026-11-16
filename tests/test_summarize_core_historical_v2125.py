import unittest
from tools.summarize_core_historical_v2125 import summarize
RUN='RUN-A4449145A6E377FF'
def fixture():
    run={'run':{'run_id':RUN,'status':'BLOCKED','mode':'DEMO'},'events':[{'evidence_ids':['E1']}],'stages':[]}
    ledger={'run_id':RUN,'analyses':[{'evidence_ids':['E1']}],'critiques':[{'evidence_ids':['E1'],'validated':False}],'policy_decisions':[{'state':'BLOCKED'}]}
    evidence={'run_id':RUN,'items':[{'evidence_id':'E1'}]}
    return run,ledger,evidence
class SummaryTests(unittest.TestCase):
    def test_summary(self):
        s=summarize(*fixture());self.assertEqual(s['event_evidence']['found_in_export'],1)
        self.assertEqual(s['critic_validation_declarations'],{'FALSE':1})
    def test_missing_reference(self):
        a=list(fixture());a[2]['items']=[]
        self.assertEqual(summarize(*a)['event_evidence']['missing_from_export'],1)
    def test_mismatch(self):
        a=list(fixture());a[1]['run_id']='different'
        with self.assertRaises(ValueError):summarize(*a)
    def test_duplicate_evidence(self):
        a=list(fixture());a[2]['items'].append({'evidence_id':'E1'})
        with self.assertRaises(ValueError):summarize(*a)
if __name__=='__main__':unittest.main()
