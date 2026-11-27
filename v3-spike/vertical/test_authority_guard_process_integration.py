"""LAB: real file-backed SQLite, distinct processes, synthetic publication journal.
No runtime wiring or production authority; journal is a test fixture, not Core.
"""
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from authority_guard_operations_candidate import AdmissionIdentity, publish_once, lookup_receipt
from authority_restore_guard_candidate import provision_witness, RestoreBlocked, snapshot, open_existing
from collector_admission_fence import initialize, provision, FenceRejected

IDENTITY = AdmissionIdentity(('synthetic-demo','NODE-CI-TEST','COLLECTOR-a'), 'a'*64, 0, 'b'*32, 'c'*64)
RUN, RECEIPT = 'RUN-0000000000000001', 'd'*64


def wait_for(path, process=None, timeout=5):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if process is not None and process.poll() is not None:
            raise AssertionError('child exited before marker')
        if time.monotonic() >= deadline:
            raise TimeoutError('marker not received')
        time.sleep(0.01)


def worker(root, mode):
    def publisher(*args):
        assert args == (IDENTITY.scope, IDENTITY.generation, IDENTITY.episode, IDENTITY.batch)
        with (root/'published.log').open('a') as log:
            log.write(RUN+'\n'); log.flush(); os.fsync(log.fileno())
        (root/'entered').touch()
        if mode == 'hold':
            wait_for(root/'release', timeout=10)
        if mode == 'kill':
            os.kill(os.getpid(), signal.SIGKILL)
        return RUN, RECEIPT
    with closing(open_existing(root/'authority.db')) as a, closing(open_existing(root/'witness.db')) as w:
        try:
            if mode == 'lookup':
                result = lookup_receipt(a,w,IDENTITY)
            else:
                result = publish_once(a,w,IDENTITY,publisher)
        except (FenceRejected, RestoreBlocked):
            return 23
        assert result['run_id'] == RUN
        return 0


class ProcessIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        with closing(sqlite3.connect(self.root/'authority.db')) as a, closing(sqlite3.connect(self.root/'witness.db')) as w:
            initialize(a); provision(a,IDENTITY.scope,IDENTITY.token); provision_witness(a,w)
    def cmd(self, mode):
        return [sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(self.root),mode]
    def run_child(self, mode, expected):
        r = subprocess.run(self.cmd(mode),capture_output=True,timeout=10)
        self.assertEqual(r.returncode,expected,r.stderr.decode(errors='replace'))
    def states(self):
        with closing(open_existing(self.root/'authority.db')) as a, closing(open_existing(self.root/'witness.db')) as w:
            return (a.execute('SELECT state FROM collector_fence').fetchone()[0],w.execute('SELECT state FROM guard').fetchone()[0])
    def backup(self, name):
        with closing(open_existing(self.root/'authority.db')) as a, closing(sqlite3.connect(self.root/name)) as b:
            a.backup(b)
    def restore(self, name):
        # Offline fixture: all connections closed, default rollback journal mode.
        os.replace(self.root/name,self.root/'authority.db')
    def publication_count(self):
        return len((self.root/'published.log').read_text().splitlines())
    def test_distinct_processes_publish_once_and_deny_lookup_during_lease(self):
        p = subprocess.Popen(self.cmd('hold'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            wait_for(self.root/'entered',p)
            self.assertEqual(self.states(),('PENDING','BUSY'))
            self.run_child('publish',23)
            self.run_child('lookup',23)
            self.assertEqual(self.publication_count(),1)
            (self.root/'release').touch()
            _,err = p.communicate(timeout=10)
            self.assertEqual(p.returncode,0,err.decode(errors='replace'))
        finally:
            if p.poll() is None: p.kill(); p.communicate()
        self.assertEqual(self.states(),('COMMITTED','READY'))
        self.run_child('lookup',0); self.run_child('publish',23)
        self.assertEqual(self.publication_count(),1)
    def test_sigkill_after_durable_publication_before_complete(self):
        self.run_child('kill',-signal.SIGKILL)
        self.assertEqual(self.publication_count(),1)
        self.assertEqual(self.states(),('PENDING','BUSY'))
        self.run_child('publish',23); self.run_child('lookup',23)
        self.assertEqual(self.publication_count(),1)
        self.assertEqual(self.states(),('PENDING','BUSY'))
    def test_actual_offline_file_replacement_by_stale_backup_blocks(self):
        self.backup('old.db'); self.run_child('publish',0)
        self.restore('old.db')
        self.assertEqual(self.states(),('ARMED','READY'))
        self.run_child('publish',23); self.run_child('lookup',23)
        self.assertEqual(self.publication_count(),1)
    def test_actual_offline_file_replacement_by_current_backup_allows_read_only(self):
        self.run_child('publish',0); self.backup('current.db'); self.restore('current.db')
        self.run_child('lookup',0); self.run_child('publish',23)
        self.assertEqual(self.publication_count(),1)
        with closing(open_existing(self.root/'authority.db')) as a, closing(open_existing(self.root/'witness.db')) as w:
            self.assertEqual(w.execute('SELECT state,digest FROM guard').fetchone(),('READY',snapshot(a)))

if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        sys.exit(worker(Path(sys.argv[2]),sys.argv[3]))
    unittest.main(verbosity=2)
