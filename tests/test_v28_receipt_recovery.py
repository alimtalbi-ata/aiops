import ast
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/"app/worker/main.py"

class ReceiptRecoveryTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=="recover_committed_critic_block")
        self.calls=[]
        self.run={"run_id":"RUN-QF132","status":"BLOCKED","version":4}
        self.receipt={
            "run_id":"RUN-QF132","status":"BLOCKED","version":4,
            "denial_hash":"test-hash","critique_id":"CRT-QF132",
            "analysis_id":"ANL-QF132","outbox_status":"PENDING",
            "current_version":4
        }
        def get(base,path,**kw):
            self.calls.append(path)
            if path.endswith("/receipt"):
                return self.receipt
            return {"run":self.run}
        self.ns={"get_json":get,"CORE":"core","ADMIN":"test-token"}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),
                     str(SRC),"exec"),self.ns)
        self.recover=self.ns["recover_committed_critic_block"]

    def test_valid_receipt(self):
        result=self.recover("RUN-QF132")
        self.assertTrue(result["recovered_from_receipt"])
        self.assertEqual(result["version"],4)
        self.assertEqual(len(self.calls),2)

    def test_run_not_blocked(self):
        self.run["status"]="RUNNING"
        self.assertIsNone(self.recover("RUN-QF132"))
        self.assertEqual(len(self.calls),1)

    def test_receipt_inconsistent(self):
        self.receipt["critique_id"]=None
        with self.assertRaisesRegex(RuntimeError,"inconsistent"):
            self.recover("RUN-QF132")

    def test_core_unavailable(self):
        def unavailable(*a,**kw):
            raise ConnectionError("synthetic_core_outage")
        self.ns["get_json"]=unavailable
        with self.assertRaises(ConnectionError):
            self.recover("RUN-QF132")

class CriticIncompleteReplayTests(unittest.TestCase):
    setUp=ReceiptRecoveryTests.setUp
    def test_completed_critic_without_block_is_fail_closed(self):
        self.run["status"]="RUNNING"
        self.ns["AtomicDenialBlockError"]=RuntimeError
        original=self.ns["get_json"]
        def get(base,path,**kw):
            result=original(base,path,**kw)
            if not path.endswith("/receipt"):
                result["events"]=[{
                    "stage":"DGX_CRITIC",
                    "event_type":"CRITIC_COMPLETED"
                }]
            return result
        self.ns["get_json"]=get
        with self.assertRaisesRegex(RuntimeError,"durable_resume"):
            self.recover("RUN-QF132")
        self.assertEqual(len(self.calls),1)
