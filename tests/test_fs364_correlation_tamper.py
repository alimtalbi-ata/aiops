"""FS364 regression: committed correlation is mandatory for Temporal admission.

No GLPI/Temporal/host calls; only in-memory SQLite.
"""
import sqlite3
import unittest
from dataclasses import replace

from app.core.fs364_correlation import Link, bind
from app.core.fs364_durable_admission import durable_resume_admissible
from app.core.fs364_temporal_admission import ResumeSnapshot

LINK = Link("fp-147-guard", "INC-147-guard", "RUN-147-guard", "EVD-147-guard", 147, "DEMO")


def waiting():
    return ResumeSnapshot(
        link=LINK, observed_fingerprint=LINK.fingerprint,
        observed_incident_id=LINK.incident_id, observed_run_id=LINK.run_id,
        observed_evidence_id=LINK.evidence_id, observed_ticket_id=147,
        observed_mode="DEMO", persisted_run_state="WAITING_HUMAN",
        policy_decision="ALLOW", human_answer_verified=True,
        approval_specific=True, authenticated=True, acl_ok=True, stop_auto=False,
    )


class CorrelationTamperTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        bind(self.db, LINK, verified_ticket=True, authenticated=True)

    def tearDown(self):
        self.db.close()

    def test_deleted_committed_link_blocks_resume(self):
        self.db.execute("DELETE FROM fs364_links WHERE fingerprint=?", (LINK.fingerprint,))
        self.db.commit()
        self.assertFalse(durable_resume_admissible(self.db, waiting()))

    def test_changed_evidence_blocks_resume(self):
        self.db.execute("UPDATE fs364_links SET evidence_id=? WHERE fingerprint=?",
                        ("EVD-other", LINK.fingerprint))
        self.db.commit()
        self.assertFalse(durable_resume_admissible(self.db, waiting()))

    def test_changed_run_blocks_resume(self):
        self.db.execute("UPDATE fs364_links SET run_id=? WHERE fingerprint=?",
                        ("RUN-other", LINK.fingerprint))
        self.db.commit()
        self.assertFalse(durable_resume_admissible(self.db, waiting()))

    def test_ambiguous_truthy_authorization_is_not_approval(self):
        for field, value in (
            ("authenticated", "true"), ("acl_ok", 1),
            ("human_answer_verified", "yes"), ("approval_specific", 1),
            ("stop_auto", ""), ("stop_auto", None),
        ):
            with self.subTest(field=field, value=value):
                self.assertFalse(durable_resume_admissible(
                    self.db, replace(waiting(), **{field: value})))

    def test_read_only_gate_does_not_modify_ledger(self):
        before = self.db.total_changes
        self.assertTrue(durable_resume_admissible(self.db, waiting()))
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
