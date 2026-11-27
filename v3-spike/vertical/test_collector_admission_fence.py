"""Real SQLite, synthetic identities and receipt; no Core/Evidence effects."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from collector_admission_fence import FenceRejected, initialize, provision, claim, complete, reconcile, rearm, archived_receipt


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.authority = self.root / 'authority.db'
        self.scope = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-one')
        self.token = secrets.token_hex(32)
        self.episode, self.batch = 'a' * 32, 'b' * 64
        self.run, self.receipt = 'RUN-0000000000000001', 'c' * 64
        with closing(sqlite3.connect(self.authority)) as db:
            initialize(db)
            provision(db, self.scope, self.token)

    def call(self, operation, *, scope=None, token=None, generation=0, episode=None, batch=None, tail=()):
        with closing(sqlite3.connect(self.authority)) as db:
            return operation(db, scope or self.scope, token or self.token, generation,
                             episode or self.episode, batch or self.batch, *tail)

    def test_rollback_and_ack_loss(self):
        journal = self.root / 'journal.db'
        old = self.root / 'old.db'
        with closing(sqlite3.connect(journal)) as db, db:
            db.execute('CREATE TABLE state (value TEXT)')
            db.execute("INSERT INTO state VALUES ('ARMED')")
        with closing(sqlite3.connect(journal)) as src, closing(sqlite3.connect(old)) as dst:
            src.backup(dst)
        self.assertEqual(self.call(claim), 'CLAIMED_NO_EXECUTION')
        with closing(sqlite3.connect(journal)) as db, db:
            db.execute("UPDATE state SET value='UNKNOWN_BLOCKED'")
        self.assertEqual(self.call(reconcile), {'state': 'UNKNOWN_BLOCKED'})
        with self.assertRaises(FenceRejected):
            self.call(claim)
        self.call(complete, tail=(self.run, self.receipt))
        self.call(complete, tail=(self.run, self.receipt))
        with closing(sqlite3.connect(old)) as src, closing(sqlite3.connect(journal)) as dst:
            src.backup(dst)
            self.assertEqual(dst.execute('SELECT value FROM state').fetchone()[0], 'ARMED')
        with self.assertRaises(FenceRejected):
            self.call(claim, episode='d' * 32)
        self.assertEqual(self.call(reconcile), {'state': 'COMMITTED', 'run_id': self.run, 'receipt_sha256': self.receipt})
        with self.assertRaises(FenceRejected):
            self.call(complete, tail=(self.run, 'd' * 64))

    def test_scope_and_generation(self):
        for options in ({'token': 'd' * 64}, {'scope': ('synthetic-demo', 'NODE-CI-OTHER', 'COLLECTOR-one')},
                        {'scope': ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-two')}, {'generation': 1},
                        {'generation': -1}, {'generation': False}):
            with self.subTest(options=options), self.assertRaises(FenceRejected):
                self.call(claim, **options)
        self.call(claim)
        with self.assertRaises(FenceRejected):
            self.call(reconcile, batch='d' * 64)

    def test_concurrent_claim_and_unavailable(self):
        def attempt(_):
            try:
                return self.call(claim)
            except FenceRejected:
                return 'REJECTED'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(attempt, range(2)), ['CLAIMED_NO_EXECUTION', 'REJECTED'])
        with closing(sqlite3.connect(':memory:')) as db, self.assertRaises(sqlite3.OperationalError):
            claim(db, self.scope, self.token, 0, self.episode, self.batch)


    def test_rearm_history_and_stale_generation(self):
        def proof(scope, generation, episode, batch, run, receipt):
            self.assertEqual((scope, generation, episode, batch, run, receipt),
                             (self.scope, 0, self.episode, self.batch, self.run, self.receipt))
            return {'admission_binding': {'scope': list(scope), 'generation': generation,
                                          'episode': episode, 'batch': batch, 'run_id': run,
                                          'receipt_sha256': receipt},
                    'recovery_observed_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'classification': 'SYNTHETIC_LAB_VERIFY', 'status': 'RECOVERED',
                    'original_run_id': run, 'comparison_run_id': 'RUN-0000000000000002',
                    'production_authorized': False, 'operational_decision': 'DENY',
                    'causality_established': False}

        def advance(reader=proof):
            with closing(sqlite3.connect(self.authority)) as db:
                return rearm(db, self.scope, self.token, 0, self.episode, self.batch,
                             read_verified_recovery=reader)

        self.call(claim)
        with self.assertRaises(FenceRejected):
            advance()
        self.call(complete, tail=(self.run, self.receipt))
        for change in ({'status': 'NOT_RECOVERED'}, {'original_run_id': 'RUN-0000000000000003'},
                       {'comparison_run_id': self.run}, {'production_authorized': True},
                       {'operational_decision': 'ALLOW'}):
            with self.subTest(change=change), self.assertRaises(FenceRejected):
                advance(lambda *args: proof(*args) | change)
        for key, value in (('scope', ['synthetic-demo','NODE-CI-OTHER','COLLECTOR-one']),
                           ('generation', 1), ('generation', False), ('episode', 'd'*32),
                           ('batch', 'e'*64), ('run_id', 'RUN-0000000000000003'),
                           ('receipt_sha256', 'f'*64)):
            with self.subTest(binding=key, value=value), self.assertRaises(FenceRejected):
                def wrong_binding(*args):
                    result = proof(*args)
                    result['admission_binding'][key] = value
                    return result
                advance(wrong_binding)
        for value in (None, '', 'not-a-time', '2026-02-30T00:00:00Z',
                      (datetime.now(timezone.utc)-timedelta(seconds=180)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                      (datetime.now(timezone.utc)+timedelta(seconds=60)).strftime('%Y-%m-%dT%H:%M:%SZ')):
            with self.subTest(observed=value), self.assertRaises(FenceRejected):
                advance(lambda *args: proof(*args) | {'recovery_observed_at': value})
        for key in ('admission_binding', 'recovery_observed_at'):
            with self.subTest(missing=key), self.assertRaises(FenceRejected):
                advance(lambda *args: {k:v for k,v in proof(*args).items() if k != key})
        self.assertEqual(self.call(reconcile), {'state':'COMMITTED', 'run_id':self.run,
                                               'receipt_sha256':self.receipt})
        def unavailable(*args):
            raise OSError('Verify unavailable')
        with self.assertRaises(OSError):
            advance(unavailable)
        self.assertEqual(advance(), 1)
        for options in ({'episode': 'd' * 32, 'batch': 'e' * 64},
                        {'generation': 1, 'batch': 'e' * 64},
                        {'generation': 1, 'episode': 'd' * 32}):
            with self.subTest(options=options), self.assertRaises(FenceRejected):
                self.call(claim, **options)
        with self.assertRaises(FenceRejected):
            advance()
        archived = self.call(archived_receipt)
        self.assertEqual((archived['run_id'], archived['receipt_sha256']), (self.run, self.receipt))
        with self.assertRaises(FenceRejected):
            self.call(archived_receipt, token='d' * 64)
        self.assertEqual(self.call(claim, generation=1, episode='d' * 32, batch='e' * 64), 'CLAIMED_NO_EXECUTION')
        with self.assertRaises(FenceRejected):
            self.call(complete, generation=1, episode='d' * 32, batch='e' * 64, tail=(self.run, self.receipt))
        self.call(complete, generation=1, episode='d' * 32, batch='e' * 64,
                  tail=('RUN-0000000000000003', 'f' * 64))
        self.assertEqual(self.call(archived_receipt), archived)


if __name__ == '__main__':
    unittest.main()
