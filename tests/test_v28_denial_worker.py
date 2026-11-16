import ast
import pathlib
import unittest
from unittest.mock import Mock

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"app/worker/main.py"

class WorkerFencingTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SOURCE.read_text())
        fn=next(n for n in tree.body
                if isinstance(n,ast.FunctionDef)
                and n.name=="reconcile_denial_batch")
        self.calls=[]
        self.log=Mock()
        item={
            "run_id":"RUN-SYNTHETIC",
            "critique_id":"CRIT-SYNTHETIC",
            "fencing_token":7,
            "policy_input":{"critic_validated":False},
        }
        self.verdict={
            "state":"BLOCKED",
            "decision":"HUMAN_APPROVAL",
        }
        def post(base,path,payload,**kwargs):
            self.calls.append((path,payload))
            if path=="/api/denial-intents/claim":
                return {"items":[item]}
            if path=="/api/policy/check":
                return self.verdict
            if path.endswith("/finalize"):
                return {"status":"RECONCILED"}
            raise AssertionError("unexpected_endpoint:"+path)

        self.ns={
            "post_json":post,
            "CORE":"core",
            "POLICY":"policy",
            "ADMIN":"test-token",
            "DENIAL_WORKER_OWNER":"worker-test",
            "log":self.log,
        }
        exec(compile(ast.Module(body=[fn],type_ignores=[]),
                     str(SOURCE),"exec"),self.ns)
        self.run=self.ns["reconcile_denial_batch"]

    def test_fenced_nominal(self):
        self.run()
        self.assertEqual(
            [p for p,_ in self.calls],
            ["/api/denial-intents/claim",
             "/api/policy/check",
             "/api/runs/RUN-SYNTHETIC/denial-intent/CRIT-SYNTHETIC/finalize"])
        self.assertEqual(self.calls[-1][1]["fencing_token"],7)

    def test_unsafe_policy_not_finalized(self):
        self.verdict["state"]="PASS"
        self.run()
        self.assertEqual(len(self.calls),2)
        self.log.warning.assert_called_once()

    def test_no_legacy_policy_write(self):
        self.run()
        paths=[p for p,_ in self.calls]
        self.assertFalse(any(
            p.endswith("/policy-record") or p.endswith("/reconciled")
            for p in paths))

if __name__=="__main__":
    unittest.main()
