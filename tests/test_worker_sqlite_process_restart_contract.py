"""Synthetic cross-process restart and rollback contract, NOT PG16/Temporal evidence.

Only SQLite in a temporary directory is touched. No GLPI, LIVE or approvals.
"""
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCHEMA = """CREATE TABLE fence (
 tenant TEXT NOT NULL, incident TEXT NOT NULL, run TEXT NOT NULL,
 attempt TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='SIMULATED_NO_EFFECT'),
 phase TEXT NOT NULL CHECK(phase='PRE_RESOLUTION'),
 receipt_sha256 TEXT NOT NULL,
 PRIMARY KEY (tenant, incident, run, attempt)
)"""

CHILD = """
import hashlib, sqlite3, sys
db, action, tenant, incident, run, attempt = sys.argv[1:]
payload = b'SIMULATED_NO_EFFECT:PRE_RESOLUTION'
digest = hashlib.sha256(payload).hexdigest()
try:
    with sqlite3.connect(db, timeout=15) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO fence VALUES (?, ?, ?, ?, ?, ?, ?)',
            (tenant, incident, run, attempt, 'SIMULATED_NO_EFFECT',
             'PRE_RESOLUTION', digest))
        if action == 'abort':
            raise RuntimeError('synthetic rollback')
except sqlite3.IntegrityError:
    sys.exit(3)
except RuntimeError:
    sys.exit(4)
"""

class CrossProcessFenceContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "fence.sqlite")
        with sqlite3.connect(self.db) as conn:
            conn.execute(SCHEMA)
        self.identity = ("TENANT-01", "INC-01", "RUN-01", "ATT-01")

    def child(self, action, identity=None):
        return subprocess.run(
            [sys.executable, "-c", CHILD, self.db, action,
             *(identity or self.identity)],
            capture_output=True, text=True, timeout=20, check=False,
        )

    def test_replay_rejected_after_interpreter_restart(self):
        self.assertEqual(self.child("commit").returncode, 0)
        self.assertEqual(self.child("commit").returncode, 3)
        with sqlite3.connect(self.db) as conn:
            rows = conn.execute("SELECT mode, phase, receipt_sha256 FROM fence").fetchall()
        self.assertEqual(rows, [(
            "SIMULATED_NO_EFFECT", "PRE_RESOLUTION",
            hashlib.sha256(b"SIMULATED_NO_EFFECT:PRE_RESOLUTION").hexdigest()
        )])

    def test_aborted_process_transaction_does_not_consume_key(self):
        self.assertEqual(self.child("abort").returncode, 4)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fence").fetchone()[0], 0)
        self.assertEqual(self.child("commit").returncode, 0)
        self.assertEqual(self.child("commit").returncode, 3)

    def test_identity_scope_survives_restart(self):
        self.assertEqual(self.child("commit").returncode, 0)
        for position in range(3):
            identity = list(self.identity)
            identity[position] += "-OTHER"
            self.assertEqual(self.child("commit", identity).returncode, 0)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fence").fetchone()[0], 4)

if __name__ == "__main__":
    unittest.main()
