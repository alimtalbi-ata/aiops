"""Reference claim tests; no Temporal or GLPI calls.

python -m unittest tests.test_fs364_resume_claim
"""
import sqlite3
import unittest
from dataclasses import replace
from app.core.fs364_correlation import Link, bind
from app.core.fs364_temporal_admission import ResumeSnapshot
from app.core.fs364_ticket_verification import Ticket147Snapshot
from app.core.fs364_resume_claim import claim_resume


class ResumeClaimTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.link = Link("fp-fs364", "INC-DEMO-FS-001",
                         "RUN-4FABD1786F107E51", "EVD-D2069BA816126499",
                         147, "DEMO")
        self.ticket = Ticket147Snapshot(147, 1, "AIOPS2-REAL-FS-20261106",
                                        "tenant-A", self.link.incident_id, True)
        self.snapshot = ResumeSnapshot(
            self.link, self.link.fingerprint, self.link.incident_id,
            self.link.run_id, self.link.evidence_id, 147, "DEMO",
            "WAITING_HUMAN", "ALLOW", True, True, True, True, False)
        bind(self.db, self.link, verified_ticket=True, authenticated=True)

    def tearDown(self):
        self.db.close()

    def claim(self, snapshot=None, ticket=None, version="v1", request="req1"):
        return claim_resume(self.db, snapshot or self.snapshot,
                            ticket or self.ticket, expected_tenant_id="tenant-A",
                            state_version=version, request_id=request)

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM fs364_resume_claims").fetchone()[0]

    def test_exact_replay_is_single_use(self):
        self.assertTrue(self.claim())
        self.assertTrue(self.claim())
        self.assertEqual(self.count(), 1)

    def test_conflicting_replay_rejected(self):
        self.assertTrue(self.claim())
        self.assertFalse(self.claim(request="req2"))
        self.assertFalse(self.claim(version="v2"))
        self.assertEqual(self.count(), 1)

    def test_created_and_policy_refusal_never_claim(self):
        self.assertFalse(self.claim(snapshot=replace(self.snapshot, persisted_run_state="CREATED")))
        self.assertFalse(self.claim(snapshot=replace(self.snapshot, policy_decision="DENY",
                                                      persisted_run_state="BLOCKED_NO_EFFECT")))
        self.assertEqual(self.count(), 0)

    def test_live_stop_auto_and_wrong_ticket_never_claim(self):
        self.assertFalse(self.claim(snapshot=replace(self.snapshot, observed_mode="LIVE")))
        self.assertFalse(self.claim(snapshot=replace(self.snapshot, stop_auto=True)))
        self.assertFalse(self.claim(ticket=replace(self.ticket, ticket_id=146)))
        self.assertEqual(self.count(), 0)

    def test_missing_glpi_verification_and_invalid_version(self):
        self.assertFalse(self.claim(ticket=replace(self.ticket, fetched_from_glpi=False)))
        self.assertFalse(self.claim(version=""))
        self.assertFalse(self.claim(request=" "))
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
