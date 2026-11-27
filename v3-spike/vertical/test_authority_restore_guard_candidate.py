import sqlite3
import signal
import subprocess
import sys
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
    def test_independent_daemon_identity_contract(self):
        from authority_restore_guard_candidate import require_independent_daemons
        self.assertTrue(require_independent_daemons('a'*64, 'b'*64))
        for authority_id, witness_id in (
            ('a'*64, 'a'*64), ('', 'b'*64), ('a'*63, 'b'*64),
            ('A'*64, 'b'*64), (None, 'b'*64),
        ):
            with self.subTest(authority=authority_id, witness=witness_id):
                with self.assertRaises(RestoreBlocked):
                    require_independent_daemons(authority_id, witness_id)


    def test_signed_distinct_daemon_attestations(self):
        import hashlib, hmac, json
        from authority_restore_guard_candidate import require_independent_daemon_attestations
        challenge='c'*64
        akey=b'A'*32
        wkey=b'W'*32
        def attest(daemon_id, role, domain, key, nonce=challenge):
            payload=json.dumps({'daemon_id':daemon_id,'challenge':nonce,'role':role,
                                'failure_domain_id':domain},
                               sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            return {'daemon_id':daemon_id,'challenge':nonce,'role':role,
                    'failure_domain_id':domain,
                    'signature':hmac.new(key,payload,hashlib.sha256).hexdigest()}
        authority=attest('a'*64,'authority','host-A',akey)
        witness=attest('b'*64,'witness','host-B',wkey)
        self.assertTrue(require_independent_daemon_attestations(authority,witness,challenge,akey,wkey))
        cases=(
            (authority,attest('a'*64,'witness','host-B',wkey),akey,wkey),
            (authority,attest('b'*64,'witness','host-A',wkey),akey,wkey),
            (authority,attest('b'*64,'witness','host-B',wkey,nonce='d'*64),akey,wkey),
            (authority,attest('b'*64,'witness','host-B',b'X'*32),akey,wkey),
            (authority,attest('b'*64,'witness','host-B',akey),akey,akey),
        )
        for a,w,ak,wk in cases:
            with self.subTest(attestation=w):
                with self.assertRaises(RestoreBlocked):
                    require_independent_daemon_attestations(a,w,challenge,ak,wk)
        tampered=dict(witness)
        tampered['failure_domain_id']='host-A'
        with self.assertRaises(RestoreBlocked):
            require_independent_daemon_attestations(authority,tampered,challenge,akey,wkey)

    def test_simultaneous_rollback_is_outside_contract(self):
        old_a=self.backup('old.db')
        old_w=self.connect('old-witness.db')
        self.w.backup(old_w)
        self.mutate()
        # Demonstrates why witness requires separate non-rollback trust domain.
        with guarded(old_a,old_w):
            self.assertEqual(claim(old_a,SCOPE,TOKEN,0,EP,BATCH),'CLAIMED_NO_EXECUTION')

    def assert_sigkill_keeps_busy(self, phase, expected_state):
        child = '''
import os
import signal
import sys
from contextlib import closing
from authority_restore_guard_candidate import open_existing, guarded
from collector_admission_fence import claim
from test_authority_restore_guard_candidate import SCOPE, TOKEN, EP, BATCH
with closing(open_existing(sys.argv[1])) as a, closing(open_existing(sys.argv[2])) as w:
    with guarded(a,w):
        if sys.argv[3] == 'after_claim':
            claim(a,SCOPE,TOKEN,0,EP,BATCH)
        os.kill(os.getpid(),signal.SIGKILL)
'''
        self.a.close()
        self.w.close()
        result=subprocess.run([sys.executable,'-B','-c',child,
                               str(self.root/'authority.db'),str(self.root/'witness.db'),phase],
                              cwd=Path(__file__).resolve().parent,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,-signal.SIGKILL,result.stderr.decode(errors='replace'))
        with closing(open_existing(self.root/'authority.db')) as a, closing(open_existing(self.root/'witness.db')) as w:
            self.assertEqual(w.execute('SELECT state FROM guard').fetchone()[0],'BUSY')
            self.assertEqual(a.execute('SELECT state FROM collector_fence').fetchone()[0],expected_state)
            self.assert_blocked(a=a,w=w)
            self.assertEqual(w.execute('SELECT state FROM guard').fetchone()[0],'BUSY')

    def test_sigkill_before_authority_mutation_keeps_busy(self):
        self.assert_sigkill_keeps_busy('before_claim','ARMED')

    def test_sigkill_after_authority_commit_keeps_busy(self):
        self.assert_sigkill_keeps_busy('after_claim','PENDING')


    def attest_fixture(self, daemon, role, key, challenge='c'*64):
        import hashlib, hmac, json
        payload = {'daemon_id': daemon, 'role': role, 'challenge': challenge,
                   'failure_domain_id': 'lab-' + role}
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return dict(payload, signature=hmac.new(key, raw, hashlib.sha256).hexdigest())

    def assert_attestation_pair(self, authority_id, witness_id, authority_key, witness_key,
                                allowed=True, challenge='c'*64):
        from authority_restore_guard_candidate import require_independent_daemon_attestations
        a = self.attest_fixture(authority_id, 'authority', authority_key, challenge)
        w = self.attest_fixture(witness_id, 'witness', witness_key, challenge)
        args = (a, w, challenge, authority_key, witness_key)
        if allowed:
            self.assertTrue(require_independent_daemon_attestations(*args))
        else:
            with self.assertRaises(RestoreBlocked):
                require_independent_daemon_attestations(*args)

    def test_canonical_uuid_direct(self):
        from authority_restore_guard_candidate import require_independent_daemons
        self.assertTrue(require_independent_daemons('12345678-1234-1234-1234-123456789abc',
                                                    '87654321-4321-4321-4321-cba987654321'))

    def test_canonical_uuid_signed(self):
        self.assert_attestation_pair('12345678-1234-1234-1234-123456789abc',
                                     '87654321-4321-4321-4321-cba987654321', b'A'*32, b'W'*32)

    def test_mixed_uuid_hex_both_roles(self):
        from authority_restore_guard_candidate import require_independent_daemons
        uuid = '12345678-1234-1234-1234-123456789abc'
        for a,w in ((uuid,'b'*64),('a'*64,uuid)):
            with self.subTest(a=a,w=w):
                self.assertTrue(require_independent_daemons(a,w))
                self.assert_attestation_pair(a,w,b'A'*32,b'W'*32)

    def test_noncanonical_uuid_rejected(self):
        from authority_restore_guard_candidate import require_independent_daemons
        uuid = '12345678-1234-1234-1234-123456789abc'
        for invalid in (uuid.upper(), uuid.replace('-',''), uuid+' ', uuid+'\n'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RestoreBlocked):
                    require_independent_daemons(invalid,'b'*64)
                self.assert_attestation_pair(invalid,'b'*64,b'A'*32,b'W'*32,False)

    def test_identical_uuid_rejected(self):
        from authority_restore_guard_candidate import require_independent_daemons
        uuid = '12345678-1234-1234-1234-123456789abc'
        with self.assertRaises(RestoreBlocked):
            require_independent_daemons(uuid,uuid)
        self.assert_attestation_pair(uuid,uuid,b'A'*32,b'W'*32,False)

    def test_hmac_zero_padding_equivalence_rejected(self):
        import hmac
        key = b'A'*32
        for n in (1,16,32):
            padded = key + b'\x00'*n
            with self.subTest(n=n):
                self.assertNotEqual(key,padded)
                self.assertEqual(hmac.digest(key,b'fixture','sha256'),
                                 hmac.digest(padded,b'fixture','sha256'))
                self.assert_attestation_pair('a'*64,'b'*64,key,padded,False)

    def test_hmac_long_key_hash_equivalence_rejected(self):
        import hashlib, hmac
        for n in (65,128):
            key = b'A'*n
            digest = hashlib.sha256(key).digest()
            with self.subTest(n=n):
                self.assertEqual(hmac.digest(key,b'fixture','sha256'),
                                 hmac.digest(digest,b'fixture','sha256'))
                self.assert_attestation_pair('a'*64,'b'*64,key,digest,False)
                self.assert_attestation_pair('a'*64,'b'*64,digest,key,False)

    def test_short_keys_and_nonhex_challenge_rejected(self):
        for a,w in ((b'A'*31,b'W'*32),(b'A'*32,b'W'*31)):
            self.assert_attestation_pair('a'*64,'b'*64,a,w,False)
        self.assert_attestation_pair('a'*64,'b'*64,b'A'*32,b'W'*32,False,
                                     '12345678-1234-1234-1234-123456789abc')


if __name__=='__main__':
    unittest.main(verbosity=2)
