"""Synthetic REJECT-only Core HTTP adversarial tests. No real GLPI or Worker."""
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import hitl_reject_delivery as m
from core import itsm_xref as x

NOW = datetime.now(timezone.utc)
OWNER = ('run', 'RUN-A', 'TEN-A', True, 'SRC-A',
         NOW - timedelta(seconds=10), NOW - timedelta(seconds=5))
HASH = 'a' * 64
CLAIM = ('EVT-A', 'PROP-A', 'RUN-A', HASH, 2, 'REJECTED', *OWNER)
ACK = {'owner': 'svc-A', 'run_id': 'RUN-A', 'proposal_id': 'PROP-A',
       'proposal_hash': HASH, 'proposal_revision': 2,
       'lease_token': 'x' * 43, 'execution_allowed': False,
       'effect_allowed': False}


class FakeDB:
    def __init__(self):
        self.claim = CLAIM
        self.ack = ('LEASED', 'svc-A', 'x' * 43, NOW + timedelta(seconds=20),
                    'PROP-A', 'RUN-A', HASH, 2, 'REJECT', 'REJECTED', *OWNER)
        self.calls = []
        self.fail = False
        self.update = True

    @contextmanager
    def db(self):
        yield self

    def execute(self, query, args):
        self.calls.append((query, args))
        if self.fail:
            raise RuntimeError('disposable database failure')
        self.last = query
        return self

    def fetchone(self):
        if self.last == m._CLAIM_SQL:
            return self.claim
        if self.last == m._LEASE_SQL:
            return (NOW + timedelta(seconds=30),) if self.update else None
        if self.last == m._ACK_SQL:
            return self.ack
        if self.last == m._DELIVER_SQL:
            return ('EVT-A',) if self.update else None
        raise AssertionError('unexpected query')


class RejectDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(m.router)
        cls.client = TestClient(app)

    def setUp(self):
        self.fake = FakeDB()
        self.db_patch = patch.object(x, 'db', self.fake.db)
        self.db_patch.start()
        self.auth_patch = patch.object(x, '_auth', side_effect=self.auth)
        self.auth_patch.start()
        self.proof_patch = patch.object(x, '_owners_attested', return_value=True)
        self.proof_patch.start()

    def tearDown(self):
        self.proof_patch.stop()
        self.auth_patch.stop()
        self.db_patch.stop()

    @staticmethod
    def auth(header):
        if header != 'Bearer good':
            return None, 401
        return {'actor_id': 'svc-A', 'tenant_ids': ['TEN-A'],
                'permissions': ['hitl:reject:deliver']}, 200

    def post(self, suffix, payload, token='good', tenant='TEN-A'):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        return self.client.post(
            f'/api/tenants/{tenant}/hitl/reject-delivery/{suffix}',
            json=payload, headers=headers)

    def test_claim_exact_binding_no_effect(self):
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'LEASED')
        item = r.json()['items'][0]
        self.assertEqual(item['proposal_hash'], HASH)
        self.assertEqual(item['proposal_revision'], 2)
        self.assertFalse(item['effect_allowed'])
        self.assertFalse(item['execution_allowed'])
        self.assertEqual(len(self.fake.calls), 2)
        self.assertEqual(self.fake.calls[0][1], ('TEN-A',))
        self.assertEqual(self.fake.calls[1][1][0], 'svc-A')
        self.assertEqual(r.headers['cache-control'], 'no-store')

    def test_claim_unauthenticated_no_db(self):
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1}, token=None)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.fake.calls, [])

    def test_claim_foreign_tenant_no_db(self):
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1}, tenant='TEN-B')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.fake.calls, [])

    def test_claim_owner_spoof_and_bad_limit_no_db(self):
        for payload in ({'owner': 'svc-B', 'limit': 1},
                        {'owner': 'svc-A', 'limit': True},
                        {'owner': 'svc-A', 'limit': 100},
                        {'owner': 'svc-A', 'limit': 1, 'approve': True}):
            r = self.post('claim', payload)
            self.assertEqual(r.json()['status'], 'UNKNOWN')
        self.assertEqual(self.fake.calls, [])

    def test_claim_no_source_proof_is_unknown(self):
        self.proof_patch.stop()
        self.proof_patch = patch.object(x, '_owners_attested', return_value=False)
        self.proof_patch.start()
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1})
        self.assertEqual(r.json()['status'], 'UNKNOWN')
        self.assertEqual(len(self.fake.calls), 1)

    def test_claim_no_rows_is_empty(self):
        self.fake.claim = None
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1})
        self.assertEqual(r.json()['items'], [])

    def test_ack_exact_delivered(self):
        r = self.post('EVT-A/ack', ACK)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'DELIVERED')
        self.assertFalse(r.json()['idempotent'])
        self.assertEqual(len(self.fake.calls), 2)

    def test_ack_idempotent_exact_binding(self):
        self.fake.ack = ('DELIVERED', *self.fake.ack[1:])
        r = self.post('EVT-A/ack', ACK)
        self.assertEqual(r.json()['status'], 'DELIVERED')
        self.assertTrue(r.json()['idempotent'])
        self.assertEqual(len(self.fake.calls), 1)

    def test_ack_rejects_wrong_token_revision_owner_and_effect(self):
        for changes in ({'lease_token': 'z'*43}, {'proposal_revision': 3},
                        {'proposal_hash': 'b'*64}, {'owner': 'svc-B'},
                        {'execution_allowed': True}, {'effect_allowed': True}):
            r = self.post('EVT-A/ack', {**ACK, **changes})
            self.assertEqual(r.json()['status'], 'UNKNOWN')
            self.assertNotIn('event_id', r.json())

    def test_ack_expired_lease_or_wrong_status_unknown(self):
        self.fake.ack = ('LEASED', *self.fake.ack[1:3],
                         NOW-timedelta(seconds=2), *self.fake.ack[4:])
        r = self.post('EVT-A/ack', ACK)
        self.assertEqual(r.json()['status'], 'UNKNOWN')
        self.assertEqual(len(self.fake.calls), 1)

    def test_ack_missing_event_non_enumerating(self):
        self.fake.ack = None
        r = self.post('EVT-FOREIGN/ack', ACK)
        self.assertEqual(r.json()['status'], 'UNKNOWN')
        self.assertNotIn('run_id', r.json())

    def test_db_failure_503(self):
        self.fake.fail = True
        r = self.post('claim', {'owner': 'svc-A', 'limit': 1})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
