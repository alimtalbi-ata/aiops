"""FS364 claim safety regressions: no external side effects.

Run: python -m unittest -v tests.test_fs364_claim_fail_closed
"""
import dataclasses
import sqlite3
import unittest

from app.core.fs364_correlation import Link, bind
from app.core.fs364_resume_claim import claim_resume
from app.core.fs364_temporal_admission import ResumeSnapshot
from app.core.fs364_ticket_verification import Ticket147Snapshot


class ClaimFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.link = Link("fp-fs364", "INC-DEMO-FS-001",
                         "RUN-4FABD1786F107E51", "EVD-D2069BA816126499",
                         147, "DEMO")
        self.ticket = Ticket147Snapshot(147, 1, "AIOPS2-REAL-FS-20261106",
                                        "tenant-A", self.link.incident_id, True)
        self.snapshot = ResumeSnapshot(
            self.link, self.link.fingerprint, self.link.incident_id,
            self.link.run_id, self.link.evidence_id, 147, "DEMO",
            "WAITING_HUMAN", "ALLOW", True, True, True, True, False)
        self.assertTrue(bind(self.conn, self.link, verified_ticket=True,
                             authenticated=True))

    def tearDown(self):
        self.conn.close()

    def claim(self, snapshot=None, request="req-1", version="v1", ticket=None):
        return claim_resume(
            self.conn, snapshot if snapshot is not None else self.snapshot,
            ticket if ticket is not None else self.ticket,
            expected_tenant_id="tenant-A", state_version=version,
            request_id=request,
        )

    def test_replay_cannot_override_revoked_policy(self):
        self.assertTrue(self.claim())
        denied = dataclasses.replace(self.snapshot, policy_decision="BLOCK")
        self.assertFalse(self.claim(denied))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM fs364_resume_claims").fetchone()[0], 1)

    def test_replay_cannot_override_terminal_state(self):
        self.assertTrue(self.claim())
        blocked = dataclasses.replace(self.snapshot, persisted_run_state="BLOCKED_NO_EFFECT")
        self.assertFalse(self.claim(blocked))

    def test_replay_cannot_override_unverified_ticket(self):
        self.assertTrue(self.claim())
        unverified = dataclasses.replace(self.ticket, fetched_from_glpi=False)
        self.assertFalse(self.claim(ticket=unverified))

    def test_conflicting_version_rejected_without_new_claim(self):
        self.assertTrue(self.claim())
        self.assertFalse(self.claim(version="v2"))
        self.assertFalse(self.claim(request="req-2"))
        self.assertEqual(self.conn.execute(
            "SELECT state_version, request_id FROM fs364_resume_claims"
        ).fetchone(), ("v1", "req-1"))


if __name__ == "__main__":
    unittest.main()
