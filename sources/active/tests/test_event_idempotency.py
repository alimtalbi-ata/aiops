"""Retry semantics: committed event receipts survive stale Temporal activity versions."""
import importlib.util
import os
import pathlib
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from fastapi import HTTPException

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
os.environ.setdefault('AIOPS_INTERNAL_TOKEN','test-token')
os.environ.setdefault('DATABASE_URL','postgresql://test:test@127.0.0.1:5432/test')
SPEC=importlib.util.spec_from_file_location('aiops_core_events',ROOT/'app'/'core'/'main.py')
CORE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CORE)

class Cursor:
    def __init__(self,result): self.result=result
    def fetchone(self): return self.result

class Connection:
    def __init__(self,previous): self.previous=previous;self.calls=[]
    def execute(self,query,parameters):
        self.calls.append((query,parameters))
        if 'from aiops.runs where run_id=%s for update' in query.lower():
            return Cursor((5,'RUNNING'))
        if 'from aiops.run_events where run_id=%s and event_key=%s' in query.lower():
            return Cursor(self.previous)
        raise AssertionError('Unexpected SQL '+query)

class TemporalEventRetryTests(unittest.TestCase):
    def setUp(self): CORE.ADMIN='test-token'

    def invoke(self,connection,stage='NORMALIZE',**fields):
        @contextmanager
        def database(): yield connection
        values=dict(expected_version=3,stage=stage,event_type='STAGE_STARTED',
                    event_key='NORMALIZE:START',status='RUNNING')
        values.update(fields)
        event=CORE.Event(**values)
        with patch.object(CORE,'db',database):
            return CORE.add_event('RUN-1',event,authorization='Bearer test-token')

    def test_duplicate_event_returns_committed_receipt_despite_stale_version(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',[],None,None,{}))
        response=self.invoke(c)
        self.assertEqual(response['version'],5)
        self.assertEqual(response['sequence'],12)
        self.assertTrue(response['idempotent'])
        self.assertEqual(len(c.calls),2)

    def test_event_key_reuse_for_different_stage_is_rejected(self):
        c=Connection((12,'POLICY','GATE_BLOCKED','BLOCKED',[],None,None,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_missing_prior_event_still_rejects_stale_version(self):
        c=Connection(None)
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)


    def test_json_encoded_receipt_is_idempotent(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING','[]',None,None,'{}'))
        self.assertTrue(self.invoke(c)['idempotent'])
        self.assertEqual(len(c.calls),2)

    def test_replay_conflicting_evidence_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',['EVD-OTHER'],None,None,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_replay_conflicting_decision_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',[],'AUTO_REMEDIATE',None,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_replay_conflicting_payload_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',[],None,None,{'unexpected':True}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_replay_conflicting_confidence_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',[],None,0.99,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_replay_conflicting_event_type_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_COMPLETED','RUNNING',[],None,None,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_replay_conflicting_status_is_rejected(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','PASS',[],None,None,{}))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_matching_evidence_and_nested_payload_replay(self):
        payload={'facts':{'z':2,'a':1},'synthetic':True}
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING',
                      '["EVD-1"]',None,0.8,
                      '{"synthetic":true,"facts":{"a":1,"z":2}}'))
        result=self.invoke(c,evidence_ids=['EVD-1'],confidence=0.8,payload=payload)
        self.assertTrue(result['idempotent'])
        self.assertEqual(result['sequence'],12)
        self.assertEqual(len(c.calls),2)

if __name__=='__main__': unittest.main()
