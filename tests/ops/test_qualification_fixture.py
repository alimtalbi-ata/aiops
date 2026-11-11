import importlib.util
import json
from pathlib import Path
import unittest
from fastapi import HTTPException

path=Path(__file__).resolve().parents[2]/'app/qualification_fixture/main.py'
spec=importlib.util.spec_from_file_location('qualification_fixture_test',path)
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

class SyntheticFixtureTests(unittest.TestCase):
    def request(self, payload, model='synthetic-ci-fixture-v1'):
        return fixture.ChatRequest(model=model,messages=[
            {'role':'system','content':'fixture'},
            {'role':'user','content':json.dumps(payload)}])

    def test_demonstration_analyst_and_critic_are_explicitly_synthetic(self):
        payload={'mode':'DEMO','incident':{'synthetic':True},
                 'evidence':[{'evidence_id':'EVID-1'}]}
        analyst=json.loads(fixture.complete(self.request(payload))['choices'][0]['message']['content'])
        self.assertEqual(analyst['severity'],'UNKNOWN')
        self.assertEqual(analyst['recommended_actions'],[])
        self.assertLess(analyst['confidence'],0.5)
        payload['analyst']=analyst
        critic=json.loads(fixture.complete(self.request(payload))['choices'][0]['message']['content'])
        self.assertEqual(critic['final_recommendation'],'OBSERVE')
        self.assertEqual(critic['claim_checks'][0]['supporting_evidence_ids'],['EVID-1'])
        self.assertIn('SYNTHETIC_CI_FIXTURE',critic['limitations'][0])

    def test_live_is_forbidden(self):
        for mode in ('LIVE','REPLAY','STORY'):
            with self.subTest(mode=mode), self.assertRaises(HTTPException) as err:
                fixture.complete(self.request({'mode':mode,'incident':{'synthetic':True},
                                               'evidence':[{'evidence_id':'E'}]}))
            self.assertEqual(err.exception.status_code,403)

    def test_missing_synthetic_provenance_is_forbidden(self):
        with self.assertRaises(HTTPException) as err:
            fixture.complete(self.request({'mode':'DEMO','incident':{},
                                           'evidence':[{'evidence_id':'E'}]}))
        self.assertEqual(err.exception.status_code,403)

    def test_unknown_model_and_missing_evidence_are_rejected(self):
        payload={'mode':'DEMO','incident':{'synthetic':True},'evidence':[{'evidence_id':'E'}]}
        with self.assertRaises(HTTPException):
            fixture.complete(self.request(payload,model='real-model'))
        payload['evidence']=[]
        with self.assertRaises(HTTPException):
            fixture.complete(self.request(payload))

if __name__=='__main__':
    unittest.main()
