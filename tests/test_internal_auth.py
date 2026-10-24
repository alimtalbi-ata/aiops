"""Boundary tests: internal Evidence and Policy APIs must deny unauthenticated calls."""
import importlib.util
import os
import pathlib
import sys
import unittest
import tempfile
from unittest.mock import patch
from fastapi import HTTPException

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
os.environ.setdefault('AIOPS_INTERNAL_TOKEN','test-only-internal-token')
os.environ.setdefault('DATABASE_URL','postgresql://test:test@127.0.0.1:5432/test')

def module(filename,slug):
    spec=importlib.util.spec_from_file_location(slug,ROOT/'app'/filename/'main.py')
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

EVIDENCE=module('evidence','aiops_evidence_auth')
POLICY=module('policy','aiops_policy_auth')

class BoundaryAuthTests(unittest.TestCase):
    def test_evidence_read_requires_auth(self):
        with patch.object(EVIDENCE,'INTERNAL_TOKEN','test-only-internal-token'):
            with self.assertRaises(HTTPException) as exc:
                EVIDENCE.search(authorization=None)
        self.assertEqual(exc.exception.status_code,401)

    def test_evidence_write_requires_auth(self):
        payload=EVIDENCE.In(source='fixture',claim='synthetic',confidence=.5)
        with patch.object(EVIDENCE,'INTERNAL_TOKEN','test-only-internal-token'):
            with self.assertRaises(HTTPException) as exc:
                EVIDENCE.create(payload,authorization='Bearer wrong')
        self.assertEqual(exc.exception.status_code,401)

    def test_policy_check_requires_auth(self):
        values=POLICY.Decision(mode='DEMO',command='EXECUTE',severity='P1',confidence=.95,
            evidence_count=2,critic_validated=True,redundancy_ok=True,
            evidence_fresh=True,freeze_active=False)
        # Explicitly isolated CI policy state; never touch the default /var/lib path.
        with tempfile.TemporaryDirectory(prefix='aiops-auth-unit-') as td, \
             patch.object(POLICY.autonomy_store,'PATH',pathlib.Path(td)/'policy.sqlite3'), \
             patch.dict(os.environ,{'AIOPS_POLICY_EMERGENCY_STOP':'false'}), \
             patch.object(POLICY,'INTERNAL_TOKEN','test-only-internal-token'):
            POLICY.autonomy_store.set_mode('NORMAL','ci-auth','isolated auth unit test baseline',0)
            with self.assertRaises(HTTPException) as exc:
                POLICY.check(values,authorization='Bearer wrong')
            valid=POLICY.check(values,authorization='Bearer test-only-internal-token')
        self.assertEqual(exc.exception.status_code,401)
        self.assertEqual(valid['decision'],'SIMULATE')

    def test_missing_secret_never_allows_requests(self):
        with patch.object(EVIDENCE,'INTERNAL_TOKEN',''):
            with self.assertRaises(HTTPException) as exc:
                EVIDENCE.authorize('Bearer anything')
        self.assertEqual(exc.exception.status_code,503)

if __name__=='__main__': unittest.main()
