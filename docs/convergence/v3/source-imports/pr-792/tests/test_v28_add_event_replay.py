import ast
import json
import pathlib
import unittest

SRC=pathlib.Path(__file__).resolve().parents[1]/'app/core/main.py'

class HTTPError(Exception):
    def __init__(self,code,detail):
        self.status_code=code
        self.detail=detail

class Result:
    def __init__(self,row):
        self.row=row
    def fetchone(self):
        return self.row

class DB:
    def __init__(self):
        self.previous=(
            8,'DGX_CRITIC','CRITIC_COMPLETED','BLOCKED',
            ['EVD-153'],'HUMAN_APPROVAL',0.9,
            {'critic_validated':False}
        )
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params):
        q=sql.lower()
        if 'from aiops.runs' in q:
            return Result((5,'RUNNING'))
        if 'from aiops.run_events' in q:
            return Result(self.previous)
        raise AssertionError('unexpected_write')

class AddEventReplayTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=='add_event')
        fn.decorator_list=[]
        self.db=DB()
        ns={
            'db':lambda:self.db,
            'auth':lambda x:None,
            'bearer':lambda x:x,
            'HTTPException':HTTPError,
            'Header':lambda **kw:None,
            'Event':object,
            'STAGES':['DGX_CRITIC'],
            'json':json,
        }
        exec(compile(ast.Module(body=[fn],type_ignores=[]),
                     str(SRC),'exec'),ns)
        self.fn=ns['add_event']

    def request(self,**updates):
        values={
            'stage':'DGX_CRITIC',
            'event_type':'CRITIC_COMPLETED',
            'status':'BLOCKED',
            'event_key':'DGX_CRITIC:COMPLETE',
            'expected_version':3,
            'evidence_ids':['EVD-153'],
            'decision':'HUMAN_APPROVAL',
            'confidence':0.9,
            'payload':{'critic_validated':False},
        }
        values.update(updates)
        return type('Request',(),values)()

    def test_identical_stale_replay(self):
        r=self.fn('RUN-153',self.request())
        self.assertTrue(r['idempotent'])
        self.assertEqual(r['version'],5)

    def test_conflicting_decision(self):
        with self.assertRaises(HTTPError) as ctx:
            self.fn('RUN-153',self.request(decision='AUTO_REMEDIATE'))
        self.assertEqual(ctx.exception.status_code,409)

    def test_conflicting_evidence(self):
        with self.assertRaises(HTTPError) as ctx:
            self.fn('RUN-153',self.request(evidence_ids=['EVD-OTHER']))
        self.assertEqual(ctx.exception.status_code,409)

    def test_conflicting_payload(self):
        with self.assertRaises(HTTPError) as ctx:
            self.fn('RUN-153',self.request(
                payload={'critic_validated':True}))
        self.assertEqual(ctx.exception.status_code,409)
