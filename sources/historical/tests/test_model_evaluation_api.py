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
os.environ.setdefault('AIOPS_INTERNAL_TOKEN','unit-test-token')
os.environ.setdefault('DATABASE_URL','postgresql://unit:unit@localhost:5432/unit')
SPEC=importlib.util.spec_from_file_location('aiops_eval_core',ROOT/'app'/'core'/'main.py')
CORE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)

def fixture():
    return CORE.ModelEvaluationIn(
        evaluation_id='EVAL-UNIT-001',dataset_version='synthetic-v1',
        dataset_hash='a'*64,provider='ci',model='ci-deterministic',
        prompt_version='analyst-v2.1+critic-v2.1',policy_version='policy-v2.0',
        retrieval_version='none',sample_count=5,metrics={'grounding':1.0},
        gate_decision='PASS',artifact_uri='reports/ai-core-evaluation.json')

class Cursor:
    def __init__(self,previous=None):
        self.previous=previous;self.result=None;self.insert=None
    def execute(self,sql,args):
        if sql.startswith('insert into aiops.model_evaluation_runs'):
            self.insert=args
            self.result=(args[0],) if self.previous is None else None
        elif sql.startswith('select dataset_version'):
            self.result=self.previous
        else:
            raise AssertionError('Unexpected SQL: '+sql)
        return self
    def fetchone(self):
        return self.result

@contextmanager
def fake_connection(cursor):
    yield cursor

class EvaluationLedgerTests(unittest.TestCase):
    def setUp(self):
        CORE.ADMIN='unit-test-token'

    def test_rejects_bad_hash_and_gate(self):
        value=fixture().model_dump()
        with self.assertRaises(Exception):
            CORE.ModelEvaluationIn(**{**value,'dataset_hash':'bad'})
        with self.assertRaises(Exception):
            CORE.ModelEvaluationIn(**{**value,'gate_decision':'EXECUTE'})

    def test_first_insert(self):
        cursor=Cursor()
        with patch.object(CORE,'db',lambda:fake_connection(cursor)):
            value=CORE.create_model_evaluation(fixture(),authorization='Bearer unit-test-token')
        self.assertFalse(value['idempotent'])
        self.assertEqual(cursor.insert[0],'EVAL-UNIT-001')

    def test_duplicate_same_content_is_idempotent(self):
        e=fixture()
        prior=(e.dataset_version,e.dataset_hash,e.provider,e.model,e.prompt_version,
               e.policy_version,e.retrieval_version,e.sample_count,e.metrics,
               e.gate_decision,e.artifact_uri)
        with patch.object(CORE,'db',lambda:fake_connection(Cursor(prior))):
            value=CORE.create_model_evaluation(e,authorization='Bearer unit-test-token')
        self.assertTrue(value['idempotent'])

    def test_duplicate_different_content_returns_conflict(self):
        e=fixture()
        prior=(e.dataset_version,e.dataset_hash,e.provider,e.model,e.prompt_version,
               e.policy_version,e.retrieval_version,e.sample_count,
               {'grounding':0.2},e.gate_decision,e.artifact_uri)
        with patch.object(CORE,'db',lambda:fake_connection(Cursor(prior))):
            with self.assertRaises(HTTPException) as error:
                CORE.create_model_evaluation(e,authorization='Bearer unit-test-token')
        self.assertEqual(error.exception.status_code,409)

    def test_authentication_required(self):
        with self.assertRaises(HTTPException) as error:
            CORE.create_model_evaluation(fixture(),authorization='Bearer wrong')
        self.assertEqual(error.exception.status_code,401)

if __name__=='__main__':
    unittest.main()
