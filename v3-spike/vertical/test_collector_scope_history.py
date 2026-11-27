"""Scope exclusivity and cross-role history regression; SQLite, synthetic Verify only."""
from datetime import datetime, timezone
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from collector_admission_fence import (FenceRejected, initialize, provision, claim, complete, rearm, reconcile, archived_receipt)

A = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-a')
B = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-b')
C = ('synthetic-demo', 'NODE-CI-OTHER', 'COLLECTOR-c')
TOKEN = 'a' * 64

def episode(n): return f'{n:032x}'
def batch(n): return f'{n:064x}'
def run(n): return f'RUN-{n:016X}'
def proof(scope, generation, ep, digest, original, receipt, comparison):
    return dict(admission_binding=dict(scope=list(scope), generation=generation, episode=ep,
                                      batch=digest, run_id=original, receipt_sha256=receipt),
                recovery_observed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                classification='SYNTHETIC_LAB_VERIFY', status='RECOVERED', original_run_id=original,
                comparison_run_id=comparison, production_authorized=False, operational_decision='DENY', causality_established=False)

class ScopeHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'authority.db'
        self.db = sqlite3.connect(self.path)
        initialize(self.db)
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def commit_episode(self, generation, n, rid):
        claim(self.db, A, TOKEN, generation, episode(n), batch(n))
        complete(self.db, A, TOKEN, generation, episode(n), batch(n), rid, batch(n + 100))
    def recovery(self, generation, n, original, comparison):
        return rearm(self.db, A, TOKEN, generation, episode(n), batch(n),
                     read_verified_recovery=lambda scope, gen, ep, digest, rid, receipt: proof(scope, gen, ep, digest, original, receipt, comparison))
    def first(self):
        provision(self.db, A, TOKEN)
        self.commit_episode(0, 1, run(1))
        self.assertEqual(self.recovery(0, 1, run(1), run(2)), 1)
    def test_owner(self):
        provision(self.db, A, TOKEN)
        with self.assertRaises(FenceRejected): provision(self.db, B, TOKEN)
        provision(self.db, C, TOKEN)
        self.assertEqual(claim(self.db, C, TOKEN, 0, episode(1), batch(1)), 'CLAIMED_NO_EXECUTION')
    def test_database_constraint(self):
        provision(self.db, A, TOKEN)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute("INSERT INTO collector_fence SELECT ?,credential,generation,state,episode,batch,run_id,receipt FROM collector_fence", ('/'.join(B),))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM collector_fence').fetchone()[0], 1)
    def test_concurrent_provision(self):
        barrier = threading.Barrier(2); results = []
        def contender(scope):
            with sqlite3.connect(self.path, timeout=5) as conn:
                barrier.wait(timeout=5)
                try: provision(conn, scope, TOKEN); results.append('accepted')
                except FenceRejected: results.append('refused')
        threads = [threading.Thread(target=contender, args=(s,)) for s in (A, B)]
        for t in threads: t.start()
        for t in threads: t.join(10)
        self.assertEqual(sorted(results), ['accepted', 'refused'])
    def test_existing_duplicate_authority_fail_closed(self):
        provision(self.db, A, TOKEN)
        with self.db:
            self.db.execute('DROP INDEX one_collector_per_target')
            self.db.execute("INSERT INTO collector_fence SELECT ?,credential,generation,state,episode,batch,run_id,receipt FROM collector_fence", ('/'.join(B),))
        for s in (A, B):
            with self.assertRaises(FenceRejected): claim(self.db, s, TOKEN, 0, episode(1), batch(1))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM collector_fence').fetchone()[0], 2)
    def test_legacy_unique_authority(self):
        provision(self.db, A, TOKEN)
        with self.db: self.db.execute('DROP INDEX one_collector_per_target')
        with self.assertRaises(FenceRejected): provision(self.db, B, TOKEN)
        self.assertEqual(claim(self.db, A, TOKEN, 0, episode(1), batch(1)), 'CLAIMED_NO_EXECUTION')
    def test_historical_incident_and_comparison_cannot_complete(self):
        self.first()
        claim(self.db, A, TOKEN, 1, episode(3), batch(3))
        for old in (run(1), run(2)):
            with self.subTest(old=old), self.assertRaises(FenceRejected):
                complete(self.db, A, TOKEN, 1, episode(3), batch(3), old, batch(103))
        self.assertEqual(reconcile(self.db, A, TOKEN, 1, episode(3), batch(3)), {'state':'UNKNOWN_BLOCKED'})
    def test_historical_incident_and_comparison_cannot_rearm(self):
        self.first(); self.commit_episode(1, 3, run(3))
        for old in (run(1), run(2)):
            with self.subTest(old=old), self.assertRaises(FenceRejected): self.recovery(1, 3, run(3), old)
        self.assertEqual(reconcile(self.db, A, TOKEN, 1, episode(3), batch(3))['state'], 'COMMITTED')
        self.assertEqual(self.recovery(1, 3, run(3), run(4)), 2)
    def test_archive_and_stale_generation(self):
        self.first()
        self.assertEqual(archived_receipt(self.db, A, TOKEN, 0, episode(1), batch(1))['comparison_run_id'], run(2))
        with self.assertRaises(FenceRejected): claim(self.db, A, TOKEN, 0, episode(3), batch(3))
    def test_scope_isolation(self):
        self.first(); provision(self.db, C, TOKEN)
        claim(self.db, C, TOKEN, 0, episode(1), batch(1))
        complete(self.db, C, TOKEN, 0, episode(1), batch(1), run(1), batch(101))
        self.assertEqual(reconcile(self.db, C, TOKEN, 0, episode(1), batch(1))['run_id'], run(1))

if __name__ == '__main__': unittest.main()
