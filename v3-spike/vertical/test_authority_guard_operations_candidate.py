import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from authority_guard_operations_candidate import AdmissionIdentity, publish_once, lookup_receipt
from authority_restore_guard_candidate import provision_witness, snapshot, RestoreBlocked, guarded
from collector_admission_fence import initialize, provision, FenceRejected, rearm
from datetime import datetime, timezone

SCOPE=('synthetic-demo','NODE-CI-TEST','COLLECTOR-a')
TOKEN='a'*64
EP='b'*32
BATCH='c'*64
RUN='RUN-0000000000000001'
RECEIPT='d'*64
IDENTITY=AdmissionIdentity(SCOPE,TOKEN,0,EP,BATCH)

class OperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.a=self.connect('authority.db'); self.w=self.connect('witness.db')
        initialize(self.a); provision(self.a,SCOPE,TOKEN); provision_witness(self.a,self.w)
        self.calls=[]
    def connect(self, name):
        c=sqlite3.connect(self.root/name,timeout=0.1); self.addCleanup(c.close); return c
    def state(self): return self.w.execute('SELECT state FROM guard').fetchone()[0]
    def publisher(self,*args):
        self.calls.append(args)
        self.assertEqual(self.state(),'BUSY')
        self.assertEqual(self.a.execute('SELECT state,episode,batch FROM collector_fence').fetchone(),('PENDING',EP,BATCH))
        return RUN,RECEIPT
    def publish(self,identity=IDENTITY,callback=None,a=None,w=None):
        return publish_once(a or self.a,w or self.w,identity,callback or self.publisher)
    def test_exact_binding_and_persisted_receipt(self):
        self.assertEqual(self.publish(),{'state':'COMMITTED','run_id':RUN,'receipt_sha256':RECEIPT})
        self.assertEqual(self.calls,[(SCOPE,0,EP,BATCH)])
        self.assertEqual(self.state(),'READY')
        self.assertEqual(self.w.execute('SELECT digest FROM guard').fetchone()[0],snapshot(self.a))
        self.assertNotIn(TOKEN,repr(IDENTITY))
    def test_bad_request_no_callback_or_poison(self):
        for identity in (replace(IDENTITY,token='0'*64),replace(IDENTITY,generation=1),replace(IDENTITY,batch='bad')):
            with self.subTest(identity=identity):
                with self.assertRaises(FenceRejected): self.publish(identity)
                self.assertEqual(self.calls,[]); self.assertEqual(self.state(),'READY')
        self.publish()
    def test_duplicate_never_publishes_twice(self):
        self.publish()
        with self.assertRaises(FenceRejected): self.publish()
        self.assertEqual(len(self.calls),1); self.assertEqual(self.state(),'READY')
    def test_publisher_exception_stays_pending_busy(self):
        def fail(*args): self.publisher(*args); raise OSError('uncertain')
        with self.assertRaises(OSError): self.publish(callback=fail)
        self.assertEqual(self.state(),'BUSY')
        self.assertEqual(self.a.execute('SELECT state FROM collector_fence').fetchone()[0],'PENDING')
        with self.assertRaises(RestoreBlocked): self.publish()
        self.assertEqual(len(self.calls),1)
    def test_invalid_verified_result_stays_busy(self):
        with self.assertRaises(RestoreBlocked): self.publish(callback=lambda *args: {'run_id':RUN})
        self.assertEqual(self.state(),'BUSY')
    def test_invalid_verified_run_stays_busy(self):
        with self.assertRaises(FenceRejected): self.publish(callback=lambda *args: ('bad',RECEIPT))
        self.assertEqual(self.state(),'BUSY')
    def test_old_snapshot_never_publishes(self):
        old=self.connect('old.db'); self.a.backup(old); self.publish()
        with self.assertRaises(RestoreBlocked): self.publish(a=old)
        self.assertEqual(len(self.calls),1); self.assertEqual(self.state(),'READY')
    def test_concurrent_publication_blocked(self):
        a=self.connect('authority.db'); w=self.connect('witness.db')
        def competing(*args):
            with self.assertRaises(RestoreBlocked): self.publish(a=a,w=w)
            return self.publisher(*args)
        self.publish(callback=competing); self.assertEqual(len(self.calls),1)
    def test_lookup_valid_and_wrong_token_no_poison(self):
        self.publish(); before=snapshot(self.a)
        self.assertEqual(lookup_receipt(self.a,self.w,IDENTITY)['run_id'],RUN)
        with self.assertRaises(FenceRejected): lookup_receipt(self.a,self.w,replace(IDENTITY,token='0'*64))
        self.assertEqual(self.state(),'READY'); self.assertEqual(snapshot(self.a),before)
    def test_lookup_old_backup_blocked(self):
        old=self.connect('old.db'); self.a.backup(old); self.publish()
        with self.assertRaises(RestoreBlocked): lookup_receipt(old,self.w,IDENTITY)
        self.assertEqual(self.state(),'READY')
    def test_lookup_during_publication_blocked(self):
        a=self.connect('authority.db'); w=self.connect('witness.db')
        def competing(*args):
            with self.assertRaises(RestoreBlocked): lookup_receipt(a,w,IDENTITY)
            return self.publisher(*args)
        self.publish(callback=competing)
    def test_lookup_archived_exact_generation(self):
        self.publish()
        def proof(scope,generation,episode,batch,run,receipt):
            return {'classification':'SYNTHETIC_LAB_VERIFY','status':'RECOVERED','original_run_id':run,
                    'comparison_run_id':'RUN-0000000000000002','production_authorized':False,
                    'operational_decision':'DENY','causality_established':False,
                    'admission_binding':{'scope':list(scope),'generation':generation,'episode':episode,'batch':batch,'run_id':run,'receipt_sha256':receipt},
                    'recovery_observed_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        with guarded(self.a,self.w): rearm(self.a,SCOPE,TOKEN,0,EP,BATCH,read_verified_recovery=proof)
        result=lookup_receipt(self.a,self.w,IDENTITY)
        self.assertEqual(result['run_id'],RUN); self.assertEqual(result['comparison_run_id'],'RUN-0000000000000002')
        self.assertEqual(self.state(),'READY')

if __name__=='__main__': unittest.main(verbosity=2)
