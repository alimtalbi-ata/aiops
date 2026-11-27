import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from collector_admission_fence import initialize, provision, claim, complete, reconcile
from authority_restore_guard_candidate import (RestoreBlocked, open_existing, provision_witness,
                                                guarded, snapshot)

SCOPE=('synthetic-demo','NODE-CI-TEST','COLLECTOR-a')
TOKEN='a'*64
EP='b'*32
BATCH='c'*64
RUN='RUN-0000000000000001'
RECEIPT='d'*64

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a=self.connect('authority.db')
        self.w=self.connect('witness.db')
        initialize(self.a)
        provision(self.a,SCOPE,TOKEN)
        provision_witness(self.a,self.w)
    def connect(self,name):
        c=sqlite3.connect(self.root/name)
        self.addCleanup(c.close)
        return c
    def backup(self,name):
        b=self.connect(name)
        self.a.backup(b)
        return b
    def mutate(self):
        with guarded(self.a,self.w):
            claim(self.a,SCOPE,TOKEN,0,EP,BATCH)
            complete(self.a,SCOPE,TOKEN,0,EP,BATCH,RUN,RECEIPT)
    def assert_blocked(self,a=None,w=None):
        with self.assertRaises((RestoreBlocked, sqlite3.Error)):
            with guarded(a or self.a,w or self.w):
                self.fail('unexpected authorization')
    def test_existing_unprotected_old_snapshot_can_reclaim(self):
        b=self.backup('old.db')
        self.mutate()
        self.assertEqual(claim(b,SCOPE,TOKEN,0,EP,BATCH),'CLAIMED_NO_EXECUTION')
    def test_old_armed_snapshot_blocked(self):
        b=self.backup('old.db')
        self.mutate()
        self.assert_blocked(a=b)
        self.assertEqual(b.execute('SELECT state FROM collector_fence').fetchone()[0],'ARMED')
    def test_old_pending_snapshot_blocked(self):
        with guarded(self.a,self.w):
            claim(self.a,SCOPE,TOKEN,0,EP,BATCH)
        b=self.backup('pending.db')
        with guarded(self.a,self.w):
            complete(self.a,SCOPE,TOKEN,0,EP,BATCH,RUN,RECEIPT)
        self.assert_blocked(a=b)
    def test_current_backup_allowed_for_read(self):
        self.mutate()
        b=self.backup('current.db')
        with guarded(b,self.w):
            self.assertEqual(reconcile(b,SCOPE,TOKEN,0,EP,BATCH)['run_id'],RUN)
    def test_crash_before_operation_keeps_busy(self):
        with self.assertRaises(RuntimeError):
            with guarded(self.a,self.w):
                raise RuntimeError('simulated interruption')
        with closing(open_existing(self.root/'witness.db')) as w:
            self.assert_blocked(w=w)
            self.assertEqual(w.execute('SELECT state FROM guard').fetchone()[0],'BUSY')
    def test_crash_after_authority_commit_keeps_busy(self):
        with self.assertRaises(RuntimeError):
            with guarded(self.a,self.w):
                claim(self.a,SCOPE,TOKEN,0,EP,BATCH)
                raise RuntimeError('simulated interruption')
        self.assert_blocked()
        self.assertEqual(self.a.execute('SELECT state FROM collector_fence').fetchone()[0],'PENDING')
    def test_parallel_connection_blocked(self):
        with closing(open_existing(self.root/'authority.db')) as a, closing(open_existing(self.root/'witness.db')) as w:
            with guarded(self.a,self.w):
                self.assert_blocked(a=a,w=w)
    def test_modified_schema_blocked(self):
        self.a.execute('DROP INDEX one_collector_per_target')
        self.assert_blocked()
    def test_missing_witness_not_auto_created(self):
        missing=self.root/'missing.db'
        with self.assertRaises(FileNotFoundError):
            open_existing(missing)
        self.assertFalse(missing.exists())
    def test_same_file_rejected(self):
        self.assert_blocked(w=self.a)
    def test_witness_cannot_be_reinitialized(self):
        with self.assertRaises(sqlite3.Error):
            provision_witness(self.a,self.w)
        with guarded(self.a,self.w):
            self.assertTrue(snapshot(self.a))
    def test_simultaneous_rollback_is_outside_contract(self):
        old_a=self.backup('old.db')
        old_w=self.connect('old-witness.db')
        self.w.backup(old_w)
        self.mutate()
        # Demonstrates why witness requires separate non-rollback trust domain.
        with guarded(old_a,old_w):
            self.assertEqual(claim(old_a,SCOPE,TOKEN,0,EP,BATCH),'CLAIMED_NO_EXECUTION')

if __name__=='__main__':
    unittest.main(verbosity=2)
