"""Actual file-backed SQLite authority/witness; server Verify reader fixtures."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from authority_guard_operations_candidate import AdmissionIdentity, publish_once, lookup_receipt
from authority_restore_guard_candidate import provision_witness, snapshot, RestoreBlocked
from collector_admission_fence import initialize, provision, FenceRejected
from guarded_collector_rearm import rearm_guarded

SCOPE = ('synthetic-demo', 'NODE-CI-TEST', 'COLLECTOR-a')
TOKEN = 'a' * 64
RUN = 'RUN-0000000000000001'
COMPARISON = 'RUN-0000000000000002'
RECEIPT = 'd' * 64
ID = AdmissionIdentity(SCOPE, TOKEN, 0, 'b' * 32, 'c' * 64)


class RearmTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.a = self.connect('authority.db')
        self.w = self.connect('witness.db')
        initialize(self.a)
        provision(self.a, SCOPE, TOKEN)
        provision_witness(self.a, self.w)
        self.calls = []

    def connect(self, name):
        db = sqlite3.connect(self.root / name, timeout=0.1)
        self.addCleanup(db.close)
        return db

    def state(self, witness=None):
        return (witness or self.w).execute('SELECT state FROM guard').fetchone()[0]

    def publish(self, admission=ID, run=RUN, receipt=RECEIPT):
        return publish_once(self.a, self.w, admission, lambda *args: (run, receipt))

    def proof(self, scope, generation, episode, batch, run, receipt):
        self.calls.append((scope, generation, episode, batch, run, receipt))
        self.assertEqual(self.state(self.connect('witness.db')), 'BUSY')
        return {'classification': 'SYNTHETIC_LAB_VERIFY', 'status': 'RECOVERED',
                'original_run_id': run, 'comparison_run_id': COMPARISON,
                'production_authorized': False, 'operational_decision': 'DENY',
                'causality_established': False,
                'admission_binding': {'scope': list(scope), 'generation': generation,
                                      'episode': episode, 'batch': batch,
                                      'run_id': run, 'receipt_sha256': receipt},
                'recovery_observed_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    def rearm(self, admission=ID, run=RUN, receipt=RECEIPT, callback=None, a=None, w=None):
        return rearm_guarded(a or self.a, w or self.w, admission,
                             expected_run_id=run, expected_receipt_sha256=receipt,
                             read_verified_recovery=callback or self.proof)

    def test_two_generations_and_archived_readback(self):
        self.publish()
        self.assertEqual(self.rearm(), {'state': 'ARMED', 'generation': 1,
                                       'production_authorized': False})
        self.assertEqual(self.state(), 'READY')
        self.assertEqual(self.w.execute('SELECT digest FROM guard').fetchone()[0], snapshot(self.a))
        self.assertEqual(lookup_receipt(self.a, self.w, ID)['comparison_run_id'], COMPARISON)
        second = replace(ID, generation=1, episode='e'*32, batch='f'*64)
        run2 = 'RUN-0000000000000003'
        self.publish(second, run2, '9'*64)
        def proof2(*args):
            return dict(self.proof(*args), comparison_run_id='RUN-0000000000000004')
        self.assertEqual(self.rearm(second, run2, '9'*64, proof2)['generation'], 2)
        self.assertEqual(self.a.execute('SELECT count(*) FROM collector_history').fetchone()[0], 2)
        self.assertEqual(self.state(), 'READY')
        self.assertEqual(len(self.calls), 2)
        with self.assertRaises(FenceRejected):
            self.rearm()
        self.assertEqual(self.state(), 'READY')
        self.assertEqual(len(self.calls), 2)

    def test_preflight_bad_receipt_token_generation_and_episode_no_poison(self):
        self.publish()
        before = snapshot(self.a)
        for admission, run, receipt in (
            (ID, RUN, '0'*64), (ID, 'RUN-0000000000000099', RECEIPT),
            (replace(ID, token='0'*64), RUN, RECEIPT),
            (replace(ID, generation=1), RUN, RECEIPT),
            (replace(ID, episode='0'*32), RUN, RECEIPT)):
            with self.subTest(admission=admission, run=run):
                with self.assertRaises(FenceRejected):
                    self.rearm(admission, run, receipt)
                self.assertEqual(self.state(), 'READY')
                self.assertEqual(snapshot(self.a), before)
        self.assertEqual(self.calls, [])

    def test_armed_is_not_committed(self):
        with self.assertRaises(FenceRejected):
            self.rearm()
        self.assertEqual(self.state(), 'READY')
        self.assertEqual(self.calls, [])

    def test_not_recovered_latches(self):
        self.publish()
        before = snapshot(self.a)
        with self.assertRaises(FenceRejected):
            self.rearm(callback=lambda *args: dict(self.proof(*args), status='NOT_RECOVERED'))
        self.assertEqual(self.state(self.connect('witness.db')), 'BUSY')
        self.assertEqual(snapshot(self.a), before)
        with self.assertRaises(RestoreBlocked):
            self.rearm()
        self.assertEqual(len(self.calls), 1)

    def test_reader_exception_latches(self):
        self.publish()
        def fail(*args):
            self.proof(*args)
            raise OSError('synthetic unavailable')
        with self.assertRaises(OSError):
            self.rearm(callback=fail)
        self.assertEqual(self.state(self.connect('witness.db')), 'BUSY')

    def test_stale_recovery_latches(self):
        self.publish()
        with self.assertRaises(FenceRejected):
            self.rearm(callback=lambda *args: dict(self.proof(*args),
                                                   recovery_observed_at='2000-01-01T00:00:00Z'))
        self.assertEqual(self.state(), 'BUSY')

    def test_concurrent_rearm_refused_before_reader(self):
        self.publish()
        a, w = self.connect('authority.db'), self.connect('witness.db')
        def compare(*args):
            with self.assertRaises(RestoreBlocked):
                self.rearm(a=a, w=w)
            return self.proof(*args)
        self.rearm(callback=compare)
        self.assertEqual(len(self.calls), 1)

    def test_lost_ack_after_authority_commit_remains_busy(self):
        self.publish()
        def fail_after_commit(db):
            if db.execute('SELECT generation FROM collector_fence').fetchone()[0] == 1:
                raise OSError('synthetic witness finalization failure')
            return snapshot(db)
        with patch('guarded_collector_rearm.snapshot', side_effect=fail_after_commit):
            with self.assertRaises(OSError):
                self.rearm()
        self.assertEqual(self.a.execute('SELECT generation,state FROM collector_fence').fetchone(),
                         (1, 'ARMED'))
        self.assertEqual(self.state(self.connect('witness.db')), 'BUSY')
        with self.assertRaises(RestoreBlocked):
            lookup_receipt(self.a, self.w, ID)

    def test_history_collision_latches_second_generation(self):
        self.publish()
        self.rearm()
        second = replace(ID, generation=1, episode='e'*32, batch='f'*64)
        run2 = 'RUN-0000000000000003'
        self.publish(second, run2, '9'*64)
        with self.assertRaises(FenceRejected):
            self.rearm(second, run2, '9'*64)
        self.assertEqual(self.state(), 'BUSY')
        self.assertEqual(self.a.execute('SELECT generation,state FROM collector_fence').fetchone(),
                         (1, 'COMMITTED'))


if __name__ == '__main__':
    unittest.main()
