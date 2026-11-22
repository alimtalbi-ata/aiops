"""Synthetic SQLite Twin/Evidence atomic boundary; never a production attestation."""
import hashlib
import os
import sqlite3
import tempfile
import threading
import unittest

SCHEMA = """
CREATE TABLE acl (tenant TEXT NOT NULL, principal TEXT NOT NULL, allowed INTEGER NOT NULL,
 PRIMARY KEY(tenant,principal));
CREATE TABLE twin (tenant TEXT NOT NULL, instance TEXT NOT NULL, revision TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(tenant,instance));
CREATE TABLE evidence (tenant TEXT NOT NULL, instance TEXT NOT NULL, event TEXT NOT NULL,
 revision TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(tenant,instance,event));
"""

def digest(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def read_atomic(conn, tenant, instance, principal, event, expected_revision, expected_digest,
                hook=None):
    """One transaction/connection for ACL and pair; DENY on any mismatch or error."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        allowed = conn.execute("SELECT allowed FROM acl WHERE tenant=? AND principal=?",
                               (tenant, principal)).fetchone()
        if allowed != (1,):
            raise PermissionError("acl")
        changes_before_hook = conn.total_changes
        if hook:
            hook()
            if conn.total_changes != changes_before_hook:
                raise PermissionError("callback wrote within read-only snapshot")
        twin = conn.execute("SELECT revision,payload FROM twin WHERE tenant=? AND instance=?",
                            (tenant, instance)).fetchone()
        ev = conn.execute(
            "SELECT revision,digest,payload FROM evidence WHERE tenant=? AND instance=? AND event=?",
            (tenant, instance, event)).fetchone()
        if not twin or not ev or twin[0] != ev[0] or twin[0] != expected_revision:
            raise PermissionError("revision")
        if ev[1] != expected_digest or digest(ev[2]) != ev[1]:
            raise PermissionError("digest")
        if conn.execute("SELECT allowed FROM acl WHERE tenant=? AND principal=?",
                        (tenant, principal)).fetchone() != (1,):
            raise PermissionError("revoked")
        conn.execute("ROLLBACK")  # read-only receipt: no mutations survive
        return ("ALLOW_SYNTHETIC", twin[1], ev[2])
    except (sqlite3.Error, PermissionError, ValueError, TypeError):
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        return ("DENY", None, None)

class AtomicBoundaryTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="v3-twin-", suffix=".db")
        os.close(fd)
        self.db = sqlite3.connect(self.path, timeout=0.05, isolation_level=None)
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT INTO acl VALUES ('t1','alice',1)")
        self.db.execute("INSERT INTO acl VALUES ('t2','alice',0)")
        self.db.execute("INSERT INTO twin VALUES ('t1','i1','r1','twin')")
        self.db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                        ('t1','i1','e1','r1',digest('proof'),'proof'))
        self.args = ('t1','i1','alice','e1','r1',digest('proof'))

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def decide(self, *args, hook=None):
        return read_atomic(self.db, *(args or self.args), hook=hook)[0]

    def test_valid(self):
        self.assertEqual(self.decide(), "ALLOW_SYNTHETIC")

    def test_cross_tenant(self):
        self.assertEqual(self.decide('t2','i1','alice','e1','r1',digest('proof')), "DENY")

    def test_wrong_instance(self):
        self.assertEqual(self.decide('t1','i2','alice','e1','r1',digest('proof')), "DENY")

    def test_wrong_principal(self):
        self.assertEqual(self.decide('t1','i1','bob','e1','r1',digest('proof')), "DENY")

    def test_wrong_event(self):
        self.assertEqual(self.decide('t1','i1','alice','opaque-other','r1',digest('proof')), "DENY")

    def test_wrong_revision(self):
        self.assertEqual(self.decide('t1','i1','alice','e1','r2',digest('proof')), "DENY")

    def test_wrong_digest(self):
        self.assertEqual(self.decide('t1','i1','alice','e1','r1',digest('tampered')), "DENY")

    def test_stored_digest_lie(self):
        self.db.execute("UPDATE evidence SET payload='tampered' WHERE event='e1'")
        self.assertEqual(self.decide(), "DENY")

    def test_revocation_before(self):
        self.db.execute("UPDATE acl SET allowed=0 WHERE tenant='t1'")
        self.assertEqual(self.decide(), "DENY")

    def test_revocation_inside_transaction(self):
        def revoke():
            self.db.execute("UPDATE acl SET allowed=0 WHERE tenant='t1'")
        self.assertEqual(self.decide(hook=revoke), "DENY")
        self.assertEqual(self.db.execute("SELECT allowed FROM acl WHERE tenant='t1'").fetchone(), (1,))

    def test_mutation_rolled_back(self):
        def mutate():
            self.db.execute("UPDATE twin SET payload='evil' WHERE tenant='t1'")
            raise PermissionError("abort")
        self.assertEqual(self.decide(hook=mutate), "DENY")
        self.assertEqual(self.db.execute("SELECT payload FROM twin WHERE tenant='t1'").fetchone(), ('twin',))

    def test_silent_twin_write_must_deny_and_rollback(self):
        def mutate():
            self.db.execute("UPDATE twin SET payload='evil' WHERE tenant='t1'")
        self.assertEqual(self.decide(hook=mutate), "DENY")
        self.assertEqual(self.db.execute("SELECT payload FROM twin WHERE tenant='t1'").fetchone(), ('twin',))

    def test_silent_acl_write_then_restore_must_deny(self):
        def mutate():
            self.db.execute("UPDATE acl SET allowed=0 WHERE tenant='t1'")
            self.db.execute("UPDATE acl SET allowed=1 WHERE tenant='t1'")
        self.assertEqual(self.decide(hook=mutate), "DENY")
        self.assertEqual(self.db.execute("SELECT allowed FROM acl WHERE tenant='t1'").fetchone(), (1,))

    def test_competing_writer_blocked_during_snapshot(self):
        barrier = threading.Event()
        results = []
        def writer():
            other = sqlite3.connect(self.path, timeout=0.02, isolation_level=None)
            try:
                barrier.wait(timeout=2)
                try:
                    other.execute("UPDATE acl SET allowed=0 WHERE tenant='t1'")
                    results.append("WRITTEN")
                except sqlite3.OperationalError as exc:
                    results.append("LOCKED" if "locked" in str(exc) else "ERROR")
            finally:
                other.close()
        thread = threading.Thread(target=writer)
        thread.start()
        def race():
            barrier.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive(), "writer must terminate")
        try:
            self.assertEqual(self.decide(hook=race), "ALLOW_SYNTHETIC")
        finally:
            thread.join(timeout=2)
        self.assertEqual(results, ["LOCKED"])
        self.assertEqual(self.db.execute("SELECT allowed FROM acl WHERE tenant='t1'").fetchone(), (1,))

if __name__ == "__main__":
    unittest.main()
