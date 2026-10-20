"""Critic schema repair regressions; no network or DGX."""
import importlib.util
import json
import pathlib
import sys
import unittest
from unittest.mock import patch, Mock
from fastapi import HTTPException

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
spec=importlib.util.spec_from_file_location("critic_v24",ROOT/"app/intelligence/main.py")
ai=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)

def critic_payload():
    return dict(validated=False,issues=[],claim_checks=[
        dict(claim="Unproven impact",supported=False,
             supporting_evidence_ids=[],contradicting_evidence_ids=[])],
        diagnostic_confidence=.3,final_recommendation="HUMAN_APPROVAL",
        unsafe_actions=["Do not auto-remediate"],limitations=["Unknown impact"])

def response(payload):
    r=Mock()
    r.raise_for_status.return_value=None
    r.json.return_value={"choices":[{"message":{"content":json.dumps(payload)}}]}
    return r

class CriticRetryTests(unittest.TestCase):
    def test_extra_field_repaired_without_dropping_objections(self):
        original=critic_payload()
        original["claim_checks"][0]["assumptions"]=["Unknown service"]
        fixed=critic_payload()
        with patch.object(ai,"BASE","http://example/v1"), patch.object(ai,"MODEL","synthetic"), patch.object(ai.requests,"post",side_effect=[response(original),response(fixed)]) as post:
            obj=ai.call_model("Critic",{"incident":{"synthetic":True}},ai.Critique)
        self.assertFalse(obj.validated)
        self.assertEqual(len(obj.claim_checks),1)
        self.assertEqual(post.call_count,2)

    def test_repair_cannot_delete_unsafe_findings(self):
        original=critic_payload()
        original["claim_checks"][0]["assumptions"]=["x"]
        fixed=critic_payload()
        fixed["unsafe_actions"]=[]
        with patch.object(ai,"BASE","http://example/v1"), patch.object(ai,"MODEL","synthetic"), patch.object(ai.requests,"post",side_effect=[response(original),response(fixed)]):
            with self.assertRaises(HTTPException) as e:
                ai.call_model("Critic",{},ai.Critique)
        self.assertEqual(e.exception.status_code,502)

    def test_valid_critic_no_retry(self):
        with patch.object(ai,"BASE","http://example/v1"), patch.object(ai,"MODEL","synthetic"), patch.object(ai.requests,"post",return_value=response(critic_payload())) as post:
            result=ai.call_model("Critic",{},ai.Critique)
        self.assertFalse(result.validated)
        self.assertEqual(post.call_count,1)

if __name__=="__main__":
    unittest.main()
