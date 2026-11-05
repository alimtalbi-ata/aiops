"""SQLite-only crash boundary contract; NOT PG16, Temporal or human HITL proof.

Separate Python processes exercise crash-before-commit and crash-after-commit.
No network, GLPI writes, LIVE effects, or automatic Temporal scheduling.
"""
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCHEMA = """CREATE TABLE receipts (
 tenant TEXT NOT NULL, incident TEXT NOT NULL, run TEXT NOT NULL,
 attempt TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='SIMULATED_NO_EFFECT'),
 phase TEXT NOT NULL CHECK(phase='PRE_RESOLUTION'),
 digest TEXT NOT NULL,
 PRIMARY KEY(tenant, incident, run, attempt)
)"""

CHILD = """
import hashlib, os, sqlite3, sys
db, boundary = sys.argv[1:]
payload = b'SIMULATED_NO_EFFECT:PRE_RESOLUTION'
digest = hashlib.sha256(payload).hexdigest()
conn = sqlite3.connect(db, timeout=10, isolation_level=None)
conn.execute('BEGIN IMMEDIATE')
try:
    conn.execute('INSERT INTO receipts VALUES (?,?,?,?,?,?,?)',
        ('TENANT-01','INC-01','RUN-01','ATT-01',
         'SIMULATED_NO_EFFECT','PRE_RESOLUTION',digest))
except sqlite3.IntegrityError:
    conn.rollback()
    sys.exit(3)
if boundary == 'before_commit':
    os._exit(71)
conn.commit()
if boundary == 'after_commit':
    os._exit(72)
conn.close()
"""

class CrashBoundaryContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "fence.sqlite")
        with sqlite3.connect(self.db) as conn:
            conn.execute(SCHEMA)

    def child(self, boundary):
        return subprocess.run(
            [sys.executable, "-c", CHILD, self.db, boundary],
            capture_output=True, text=True, timeout=20, check=False,
        )

    def rows(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(
                "SELECT tenant,incident,run,attempt,mode,phase,digest FROM receipts"
            ).fetchall()

    def expected(self):
        return [(
            'TENANT-01','INC-01','RUN-01','ATT-01',
            'SIMULATED_NO_EFFECT','PRE_RESOLUTION',
            hashlib.sha256(b'SIMULATED_NO_EFFECT:PRE_RESOLUTION').hexdigest()
        )]

    def test_process_crash_before_commit_releases_key(self):
        self.assertEqual(self.child('before_commit').returncode, 71)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.child('commit').returncode, 0)
        self.assertEqual(self.rows(), self.expected())
        self.assertEqual(self.child('commit').returncode, 3)

    def test_process_crash_after_commit_preserves_replay_fence(self):
        self.assertEqual(self.child('after_commit').returncode, 72)
        self.assertEqual(self.rows(), self.expected())
        self.assertEqual(self.child('commit').returncode, 3)
        self.assertEqual(self.rows(), self.expected())

if __name__ == '__main__':
    unittest.main()
