from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from authority_restore_guard_candidate import guarded, provision_witness, RestoreBlocked, snapshot
from authority_guard_preflight_candidate import guarded_claim
from collector_admission_fence import initialize, provision, claim, complete, FenceRejected, rearm
from datetime import datetime, timezone

SCOPE=('synthetic-demo','NODE-CI-TEST','COLLECTOR-a')
TOKEN='a'*64
EP='b'*32
BATCH='c'*64
RUN='RUN-0000000000000001'
RECEIPT='d'*64

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a=self.connect('a.db'); self.w=self.connect('w.db')
        initialize(self.a); provision(self.a,SCOPE,TOKEN); provision_witness(self.a,self.w)
    def connect(self,name):
        c=sqlite3.connect(self.root/name); self.addCleanup(c.close); return c
    def state(self): return self.w.execute('SELECT state FROM guard').fetchone()[0]
    def lease(self, *, a=None,w=None,token=TOKEN,generation=0,episode=EP,batch=BATCH,scope=SCOPE):
        return guarded_claim(a or self.a,w or self.w,scope,token,generation,episode,batch)
    def good(self):
        with self.lease():
            claim(self.a,SCOPE,TOKEN,0,EP,BATCH)
            complete(self.a,SCOPE,TOKEN,0,EP,BATCH,RUN,RECEIPT)
    def test_existing_naive_wrapper_poison_on_bad_token(self):
        with self.assertRaises(FenceRejected):
            with guarded(self.a,self.w): claim(self.a,SCOPE,'0'*64,0,EP,BATCH)
        self.assertEqual(self.state(),'BUSY')
    def test_wrong_token_no_poison(self):
        with self.assertRaises(FenceRejected):
            with self.lease(token='0'*64): self.fail('accepted')
        self.assertEqual(self.state(),'READY'); self.good()
    def test_wrong_generation_no_poison(self):
        with self.assertRaises(FenceRejected):
            with self.lease(generation=1): self.fail('accepted')
        self.assertEqual(self.state(),'READY'); self.good()
    def test_bad_episode_no_poison(self):
        with self.assertRaises(FenceRejected):
            with self.lease(episode='invalid'): self.fail('accepted')
        self.assertEqual(self.state(),'READY'); self.good()
    def test_wrong_scope_no_poison(self):
        with self.assertRaises(FenceRejected):
            with self.lease(scope=('synthetic-demo','NODE-CI-OTHER','COLLECTOR-a')): self.fail('accepted')
        self.assertEqual(self.state(),'READY'); self.good()
    def test_repeated_claim_no_poison(self):
        self.good()
        with self.assertRaises(FenceRejected):
            with self.lease(): self.fail('accepted')
        self.assertEqual(self.state(),'READY')
    def test_old_backup_rejected_before_preflight(self):
        b=self.connect('old.db'); self.a.backup(b); self.good()
        with self.assertRaises(RestoreBlocked):
            with self.lease(a=b): self.fail('accepted')
        self.assertEqual(self.state(),'READY')
    def test_after_claim_exception_stays_busy(self):
        with self.assertRaises(OSError):
            with self.lease():
                claim(self.a,SCOPE,TOKEN,0,EP,BATCH); raise OSError('publisher uncertain')
        self.assertEqual(self.state(),'BUSY')
        self.assertEqual(self.a.execute('SELECT state FROM collector_fence').fetchone()[0],'PENDING')
        with self.assertRaises(RestoreBlocked):
            with self.lease(): self.fail('accepted')
    def test_competing_connection_blocked(self):
        a=self.connect('a.db'); w=self.connect('w.db')
        with self.lease():
            with self.assertRaises(RestoreBlocked):
                with self.lease(a=a,w=w): self.fail('accepted')
            claim(self.a,SCOPE,TOKEN,0,EP,BATCH)
        self.assertEqual(self.state(),'READY')
    def test_success_updates_witness(self):
        self.good(); self.assertEqual(self.state(),'READY')
        self.assertEqual(self.w.execute('SELECT digest FROM guard').fetchone()[0],snapshot(self.a))
    def test_historical_replay_no_poison(self):
        self.good()
        def proof(scope,generation,episode,batch,run,receipt):
            return {'classification':'SYNTHETIC_LAB_VERIFY','status':'RECOVERED','original_run_id':run,
                    'comparison_run_id':'RUN-0000000000000002','production_authorized':False,
                    'operational_decision':'DENY','causality_established':False,
                    'admission_binding':{'scope':list(scope),'generation':generation,'episode':episode,'batch':batch,'run_id':run,'receipt_sha256':receipt},
                    'recovery_observed_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        with guarded(self.a,self.w): rearm(self.a,SCOPE,TOKEN,0,EP,BATCH,read_verified_recovery=proof)
        with self.assertRaises(FenceRejected):
            with self.lease(generation=1): self.fail('accepted')
        self.assertEqual(self.state(),'READY')
        with self.lease(generation=1,episode='e'*32,batch='f'*64):
            claim(self.a,SCOPE,TOKEN,1,'e'*32,'f'*64)
        self.assertEqual(self.state(),'READY')

if __name__=='__main__': unittest.main(verbosity=2)
