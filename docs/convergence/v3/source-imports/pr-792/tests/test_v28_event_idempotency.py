import ast
import json
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/"app/core/main.py"

class Result:
    def __init__(self,row):
        self.row=row
    def fetchone(self):
        return self.row

class FakeConnection:
    def __init__(self,old):
        self.old=old
        self.queries=[]
    def execute(self,sql,params):
        self.queries.append(sql)
        if 'from aiops.run_events' in sql:
            return Result(self.old)
        if 'from aiops.runs' in sql:
            return Result((4,))
        raise AssertionError('unexpected_write')

class EventIdempotencyTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body
                if isinstance(n,ast.FunctionDef) and n.name=="append_event")
        ns={"json":json}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),
                     str(SRC),"exec"),ns)
        self.append=ns["append_event"]
        self.old=(
            7,"DGX_CRITIC","CRITIC_COMPLETED","BLOCKED",
            json.dumps(["EVD-1"]),"HUMAN_APPROVAL",0.9,
            json.dumps({"critic_validated":False})
        )

    def execute(self,**changes):
        arguments={
            "stage":"DGX_CRITIC",
            "etype":"CRITIC_COMPLETED",
            "status":"BLOCKED",
            "eids":["EVD-1"],
            "decision":"HUMAN_APPROVAL",
            "confidence":0.9,
            "payload":{"critic_validated":False},
            "event_key":"DGX_CRITIC:COMPLETE",
        }
        arguments.update(changes)
        return self.append(FakeConnection(self.old),"RUN-1",**arguments)

    def test_identical_replay(self):
        self.assertEqual(self.execute(),(7,4,True))

    def test_status_conflict(self):
        with self.assertRaisesRegex(ValueError,"event_idempotency_conflict"):
            self.execute(status="PASS")

    def test_evidence_conflict(self):
        with self.assertRaisesRegex(ValueError,"event_idempotency_conflict"):
            self.execute(eids=["EVD-2"])

    def test_decision_conflict(self):
        with self.assertRaisesRegex(ValueError,"event_idempotency_conflict"):
            self.execute(decision="AUTO_REMEDIATE")

    def test_payload_conflict(self):
        with self.assertRaisesRegex(ValueError,"event_idempotency_conflict"):
            self.execute(payload={"critic_validated":True})
