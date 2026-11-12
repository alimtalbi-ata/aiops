"""Cross-connection SQLite claim regression; reference adapter only.

Run: python -m unittest -v tests.test_fs364_claim_concurrency
No GLPI, Temporal, Worker or filesystem lab side effects.
"""
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.core.fs364_correlation import Link, bind
from app.core.fs364_resume_claim import claim_resume
from app.core.fs364_temporal_admission import ResumeSnapshot
from app.core.fs364_ticket_verification import Ticket147Snapshot


class CrossConnectionClaimTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="fs364-claim-", suffix=".sqlite3")
        os.close(fd)
        self.link = Link("fp-fs364", "INC-DEMO-FS-001",
                         "RUN-4FABD1786F107E51", "EVD-D2069BA816126499",
                         147, "DEMO")
        self.ticket = Ticket147Snapshot(147, 1, "AIOPS2-REAL-FS-20261106",
                                        "tenant-A", self.link.incident_id, True)
        self.snapshot = ResumeSnapshot(
            self.link, self.link.fingerprint, self.link.incident_id,
            self.link.run_id, self.link.evidence_id, 147, "DEMO",
            "WAITING_HUMAN", "ALLOW", True, True, True, True, False)
        with sqlite3.connect(self.path) as conn:
            self.assertTrue(bind(conn, self.link, verified_ticket=True,
                                 authenticated=True))

    def tearDown(self):
        os.unlink(self.path)

    def claim(self, request):
        with sqlite3.connect(self.path, timeout=15) as conn:
            return claim_resume(conn, self.snapshot, self.ticket,
                                expected_tenant_id="tenant-A",
                                state_version="v1", request_id=request)

    def count(self):
        with sqlite3.connect(self.path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM fs364_resume_claims"
            ).fetchone()[0]

    def test_distinct_concurrent_requests_only_one_claims(self):
        barrier = threading.Barrier(4)
        def contender(i):
            barrier.wait(timeout=10)
            return self.claim("request-" + str(i))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(contender, range(4)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.count(), 1)

    def test_same_request_replay_across_connections(self):
        self.assertTrue(self.claim("same-request"))
        # Even an identical retry must never be treated as a new dispatch grant.
        self.assertFalse(self.claim("same-request"))
        self.assertFalse(self.claim("different-request"))
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
