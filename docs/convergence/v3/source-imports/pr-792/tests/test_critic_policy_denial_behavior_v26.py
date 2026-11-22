"""Behavioural checks for the rejected-Critic Policy denial helper, offline."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).resolve().parents[1]/"app/worker/main.py"
tree=ast.parse(SOURCE.read_text())
fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="persist_critic_denial")
isolated=compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),"exec")

class CriticDenialBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def post(base,path,data,**kwargs):
            self.calls.append((base,path,data))
            if path=="/api/policy/check":
                return {"state":"BLOCKED","decision":"HUMAN_APPROVAL","reason":"critic rejected"}
            if path.endswith("/policy-record"):
                return {"policy_decision_id":"POL-TEST"}
            return {"state":"BLOCKED"}
        self.ns={"post_json":post,"POLICY":"http://policy","CORE":"http://core",
                 "assess_evidence_freshness":lambda e:{"status":"FRESH"}}
        exec(isolated,self.ns)
        self.args=("RUN-TEST","DEMO",{"severity":"P1","confidence":.9},
                   {"validated":False,"diagnostic_confidence":.4},
                   "ANL-TEST","CRT-TEST",
                   [{"evidence_id":"EVD-002"},{"evidence_id":"EVD-001"}],"test-token")

    def test_denial_persisted_with_relationships_and_no_human_approval(self):
        result=self.ns["persist_critic_denial"](*self.args)
        self.assertEqual(result,"POL-TEST")
        self.assertEqual([p for _,p,_ in self.calls],
                         ["/api/policy/check","/api/runs/RUN-TEST/policy-record","/api/runs/RUN-TEST/gates"])
        policy=self.calls[0][2]
        self.assertFalse(policy["critic_validated"])
        self.assertFalse(policy["human_approved"])
        self.assertFalse(policy["fencing_verified"])
        record=self.calls[1][2]
        self.assertEqual(record["analysis_id"],"ANL-TEST")
        self.assertEqual(record["critique_id"],"CRT-TEST")
        self.assertEqual(record["evidence_ids"],["EVD-001","EVD-002"])
        self.assertEqual(record["policy"]["state"],"BLOCKED")

    def test_policy_pass_is_rejected_without_ledger_write(self):
        def bad(base,path,data,**kwargs):
            self.calls.append((base,path,data))
            return {"state":"PASS","decision":"SIMULATE"}
        self.ns["post_json"]=bad
        with self.assertRaisesRegex(RuntimeError,"unsafe_policy_response"):
            self.ns["persist_critic_denial"](*self.args)
        self.assertEqual(len(self.calls),1)

    def test_policy_unavailable_prevents_false_audit_success(self):
        def down(*args,**kwargs): raise TimeoutError("synthetic failure")
        self.ns["post_json"]=down
        with self.assertRaises(TimeoutError):
            self.ns["persist_critic_denial"](*self.args)

if __name__=="__main__":unittest.main()
