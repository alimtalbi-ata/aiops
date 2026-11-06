"""SQLite reference integration: no GLPI, Temporal, or filesystem effects."""
import sqlite3
import unittest
from dataclasses import replace
from app.core.fs364_correlation import Link, bind
from app.core.fs364_temporal_admission import ResumeSnapshot
from app.core.fs364_durable_admission import durable_resume_admissible

LINK = Link("fp-147", "INC-147", "RUN-147", "EVD-147", 147, "DEMO")


def snapshot(link=LINK):
    return ResumeSnapshot(
        link=link, observed_fingerprint=link.fingerprint,
        observed_incident_id=link.incident_id, observed_run_id=link.run_id,
        observed_evidence_id=link.evidence_id, observed_ticket_id=link.ticket_id,
        observed_mode=link.mode, persisted_run_state="WAITING_HUMAN",
        policy_decision="ALLOW", human_answer_verified=True,
        approval_specific=True, authenticated=True, acl_ok=True, stop_auto=False,
    )


class DurableAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_no_row_never_admitted_even_with_positive_snapshot(self):
        self.assertFalse(durable_resume_admissible(self.db, snapshot()))

    def test_exact_committed_row_is_eligible_without_resuming(self):
        bind(self.db, LINK, verified_ticket=True, authenticated=True)
        self.assertTrue(durable_resume_admissible(self.db, snapshot()))
        self.assertEqual(self.db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)

    def test_policy_refusal_and_stop_auto_remain_terminal(self):
        bind(self.db, LINK, verified_ticket=True, authenticated=True)
        for changes in ({"policy_decision": "BLOCKED"},
                        {"persisted_run_state": "BLOCKED_NO_EFFECT"},
                        {"stop_auto": True},
                        {"observed_ticket_id": 146}):
            with self.subTest(changes=changes):
                self.assertFalse(durable_resume_admissible(
                    self.db, replace(snapshot(), **changes)))

    def test_wrong_link_or_mode_is_rejected(self):
        bind(self.db, LINK, verified_ticket=True, authenticated=True)
        for changed in (replace(LINK, evidence_id="EVD-other"),
                        replace(LINK, mode="LIVE"),
                        replace(LINK, run_id="RUN-other")):
            with self.subTest(changed=changed):
                self.assertFalse(durable_resume_admissible(self.db, snapshot(changed)))

    def test_replay_does_not_duplicate_and_admission_does_not_write(self):
        bind(self.db, LINK, verified_ticket=True, authenticated=True)
        bind(self.db, LINK, verified_ticket=True, authenticated=True)
        before = self.db.total_changes
        self.assertTrue(durable_resume_admissible(self.db, snapshot()))
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(self.db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
