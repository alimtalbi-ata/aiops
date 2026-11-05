"""Synthetic persistence contract for a future PG16/Temporal idempotency adapter.

SQLite is an isolated test double, NOT evidence of PG16, Temporal, Core #233,
or a deployed durable fence. No live actions, GLPI writes or approvals.
"""
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path


SCHEMA = """
CREATE TABLE attempts (
 tenant TEXT NOT NULL, incident TEXT NOT NULL, run TEXT NOT NULL,
 attempt TEXT NOT NULL, receipt_sha256 TEXT NOT NULL,
 PRIMARY KEY (tenant, incident, run, attempt)
);
"""


def reserve(db, identity, receipt):
    # The receipt is deliberately a synthetic no-effect payload.
    assert receipt == b"SIMULATED_NO_EFFECT:PRE_RESOLUTION"
    digest = hashlib.sha256(receipt).hexdigest()
    try:
        with sqlite3.connect(db, timeout=10) as conn:
            conn.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?)",
                         (*identity, digest))
        return True
    except sqlite3.IntegrityError:
        return False


class SyntheticDurableFenceContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "fence.sqlite")
        with sqlite3.connect(self.db) as conn:
            conn.executescript(SCHEMA)
        self.identity = ("TENANT-01", "INC-01", "RUN-01", "ATT-01")
        self.receipt = b"SIMULATED_NO_EFFECT:PRE_RESOLUTION"

    def test_replay_after_new_connection_is_denied(self):
        self.assertTrue(reserve(self.db, self.identity, self.receipt))
        self.assertFalse(reserve(self.db, self.identity, self.receipt))
        with sqlite3.connect(self.db) as conn:
            rows = conn.execute("SELECT receipt_sha256 FROM attempts").fetchall()
        self.assertEqual(rows, [(hashlib.sha256(self.receipt).hexdigest(),)])

    def test_same_key_concurrency_has_single_winner(self):
        barrier = threading.Barrier(8)
        outcomes = []
        lock = threading.Lock()

        def contender():
            barrier.wait(timeout=10)
            result = reserve(self.db, self.identity, self.receipt)
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=contender) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 7)

    def test_rollback_does_not_consume_key(self):
        with self.assertRaises(RuntimeError):
            with sqlite3.connect(self.db) as conn:
                conn.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?)",
                             (*self.identity, hashlib.sha256(self.receipt).hexdigest()))
                raise RuntimeError("synthetic failure before commit")
        self.assertTrue(reserve(self.db, self.identity, self.receipt))

    def test_tenant_incident_run_are_part_of_key(self):
        self.assertTrue(reserve(self.db, self.identity, self.receipt))
        for index in (0, 1, 2):
            identity = list(self.identity)
            identity[index] += "-OTHER"
            self.assertTrue(reserve(self.db, tuple(identity), self.receipt))


if __name__ == "__main__":
    unittest.main()
