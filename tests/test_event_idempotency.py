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
        if 'from aiops.runs where run_id=%s for update' in query:
            return Cursor((5,'RUNNING'))
        if 'from aiops.run_events where run_id=%s and event_key=%s' in query:
            return Cursor(self.previous)
        raise AssertionError('Unexpected SQL '+query)

class TemporalEventRetryTests(unittest.TestCase):
    def setUp(self): CORE.ADMIN='test-token'

    def invoke(self,connection,stage='NORMALIZE'):
        @contextmanager
        def database(): yield connection
        event=CORE.Event(expected_version=3,stage=stage,event_type='STAGE_STARTED',
                         event_key='NORMALIZE:START',status='RUNNING')
        with patch.object(CORE,'db',database):
            return CORE.add_event('RUN-1',event,authorization='Bearer test-token')

    def test_duplicate_event_returns_committed_receipt_despite_stale_version(self):
        c=Connection((12,'NORMALIZE','STAGE_STARTED','RUNNING'))
        response=self.invoke(c)
        self.assertEqual(response['version'],5)
        self.assertEqual(response['sequence'],12)
        self.assertTrue(response['idempotent'])
        self.assertEqual(len(c.calls),2)

    def test_event_key_reuse_for_different_stage_is_rejected(self):
        c=Connection((12,'POLICY','GATE_BLOCKED','BLOCKED'))
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

    def test_missing_prior_event_still_rejects_stale_version(self):
        c=Connection(None)
        with self.assertRaises(HTTPException) as ctx:
            self.invoke(c)
        self.assertEqual(ctx.exception.status_code,409)

if __name__=='__main__': unittest.main()
