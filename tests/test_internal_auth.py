"""Boundary tests: internal Evidence and Policy APIs must deny unauthenticated calls."""
import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
os.environ.setdefault('AIOPS_INTERNAL_TOKEN','test-only-internal-token')
os.environ.setdefault('AIOPS_ADMIN_TOKEN','test-only-admin-token')
os.environ.setdefault('AIOPS_POLICY_STATE_DB', str(pathlib.Path(tempfile.gettempdir()) / f'aiops-policy-auth-{os.getpid()}.sqlite3'))
os.environ.setdefault('DATABASE_URL','postgresql://test:test@127.0.0.1:5432/test')

def module(filename,slug):
    spec=importlib.util.spec_from_file_location(slug,ROOT/'app'/filename/'main.py')
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

EVIDENCE=module('evidence','aiops_evidence_auth')
POLICY=module('policy','aiops_policy_auth')
TWIN=module('twin','aiops_twin_auth')

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
            evidence_count=2,critic_validated=True,redundancy_ok=True,evidence_fresh=True)
        with patch.object(POLICY,'INTERNAL_TOKEN','test-only-internal-token'):
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


    def test_twin_all_topology_reads_deny_anonymous_before_db(self):
        routes = [
            (TWIN.acme_quality, {}),
            (TWIN.summary, {}),
            (TWIN.nodes, {}),
            (TWIN.graph, {}),
            (TWIN.at, {'known_at': '2026-10-29T00:00:00Z'}),
        ]
        with patch.object(TWIN, 'db') as db:
            for handler, kwargs in routes:
                with self.subTest(handler=handler.__name__):
                    with self.assertRaises(HTTPException) as exc:
                        handler(authorization=None, **kwargs)
                    self.assertEqual(exc.exception.status_code, 401)
            db.assert_not_called()

    def test_twin_topology_read_accepts_only_explicit_bearer(self):
        with patch.object(TWIN, 'SIM_TOKEN', 'test-only-admin-token'):
            for header in ('test-only-admin-token', 'Bearer wrong', None):
                with self.assertRaises(HTTPException) as exc:
                    TWIN.require_twin_read_auth(header)
                self.assertEqual(exc.exception.status_code, 401)
            TWIN.require_twin_read_auth('Bearer test-only-admin-token')
            TWIN.require_twin_read_auth('Bearer test-only-internal-token')

    def test_twin_synthetic_noop_refused_before_database(self):
        with patch.object(TWIN, 'SIM_TOKEN', 'test-only-admin-token'), patch.object(TWIN, 'db') as db:
            for action, target in [('NOOP', 'ACME-SAN-FABRIC-A'),
                                   ('SET_STATE', None),
                                   ('OBSERVE', '  ')]:
                event = TWIN.SyntheticEvent(action=action, target_node_id=target,
                                            run_id='RUN-TEST', payload={})
                with self.subTest(action=action, target=target):
                    with self.assertRaises(HTTPException) as exc:
                        TWIN.synthetic_event(event, authorization='Bearer test-only-admin-token')
                    self.assertEqual(exc.exception.status_code, 422)
            db.assert_not_called()

    def test_twin_synthetic_unknown_target_does_not_write(self):
        with patch.object(TWIN, 'SIM_TOKEN', 'test-only-admin-token'), patch.object(TWIN, 'db') as db:
            db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
            event = TWIN.SyntheticEvent(action='SET_STATE', target_node_id='ACME-MISSING',
                                        run_id='RUN-TEST', payload={'state': 'DEGRADED'})
            with self.assertRaises(HTTPException) as exc:
                TWIN.synthetic_event(event, authorization='Bearer test-only-admin-token')
            self.assertEqual(exc.exception.status_code, 404)
            self.assertEqual(db.return_value.__enter__.return_value.execute.call_count, 1)

if __name__=='__main__': unittest.main()
