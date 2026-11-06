"""Run: python -m unittest tests.test_fs364_verified_resume"""
import sqlite3
import unittest
from dataclasses import replace
from app.core.fs364_correlation import Link, SCHEMA, bind
from app.core.fs364_temporal_admission import ResumeSnapshot
from app.core.fs364_ticket_verification import Ticket147Snapshot
from app.core.fs364_verified_resume import verified_durable_resume_admissible


class VerifiedResumeTests(unittest.TestCase):
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

    def tearDown(self):
        self.conn.close()

    def allowed(self, snapshot=None, ticket=None, tenant="tenant-A"):
        return verified_durable_resume_admissible(
            self.conn, snapshot or self.snapshot, ticket or self.ticket,
            expected_tenant_id=tenant)

    def test_missing_durable_binding_denied(self):
        self.assertFalse(self.allowed())

    def test_exact_binding_and_replay_only(self):
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        self.assertTrue(self.allowed())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM fs364_links").fetchone()[0], 1)

    def test_ticket_146_and_tenant_mismatch_denied(self):
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        self.assertFalse(self.allowed(ticket=replace(self.ticket, ticket_id=146)))
        self.assertFalse(self.allowed(tenant="tenant-B"))

    def test_policy_refusal_and_created_denied(self):
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        self.assertFalse(self.allowed(snapshot=replace(
            self.snapshot, policy_decision="DENY", persisted_run_state="BLOCKED_NO_EFFECT")))
        self.assertFalse(self.allowed(snapshot=replace(self.snapshot, persisted_run_state="CREATED")))

    def test_stop_auto_and_live_denied(self):
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        self.assertFalse(self.allowed(snapshot=replace(self.snapshot, stop_auto=True)))
        self.assertFalse(self.allowed(snapshot=replace(self.snapshot, observed_mode="LIVE")))
        self.assertFalse(self.allowed(snapshot=replace(self.snapshot, link=replace(self.link, mode="LIVE"))))

    def test_no_authoritative_glpi_read_denied(self):
        bind(self.conn, self.link, verified_ticket=True, authenticated=True)
        self.assertFalse(self.allowed(ticket=replace(self.ticket, fetched_from_glpi=False)))


if __name__ == "__main__":
    unittest.main()
