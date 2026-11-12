"""No network, Temporal or GLPI calls: deterministic fail-closed admission."""
import unittest
from dataclasses import replace
from app.core.fs364_correlation import Link
from app.core.fs364_temporal_admission import ResumeSnapshot, resume_admissible

LINK = Link("fingerprint-147", "INC-147", "RUN-147", "EVD-147", 147, "DEMO")


def waiting():
    return ResumeSnapshot(
        link=LINK, observed_fingerprint=LINK.fingerprint,
        observed_incident_id=LINK.incident_id, observed_run_id=LINK.run_id,
        observed_evidence_id=LINK.evidence_id, observed_ticket_id=147,
        observed_mode="DEMO", persisted_run_state="WAITING_HUMAN",
        policy_decision="ALLOW", human_answer_verified=True,
        approval_specific=True, authenticated=True, acl_ok=True, stop_auto=False,
    )


class TemporalAdmissionTests(unittest.TestCase):
    def test_verified_wait_is_eligible_but_does_not_resume(self):
        self.assertTrue(resume_admissible(waiting()))

    def test_terminal_and_unstarted_states_cannot_resume(self):
        for state in ("CREATED", "OBSERVE", "POLICY", "BLOCKED_NO_EFFECT",
                      "RESOLVED", "FAILED", "", None):
            with self.subTest(state=state):
                self.assertFalse(resume_admissible(replace(waiting(), persisted_run_state=state)))

    def test_mismatched_identifiers_and_ticket_fail_closed(self):
        for field, value in (("observed_fingerprint", "other"),
                             ("observed_incident_id", "other"),
                             ("observed_run_id", "other"),
                             ("observed_evidence_id", "other"),
                             ("observed_ticket_id", 146),
                             ("observed_mode", "LIVE")):
            with self.subTest(field=field):
                self.assertFalse(resume_admissible(replace(waiting(), **{field: value})))

    def test_policy_stop_auto_human_and_acl_are_independent(self):
        for field, value in (("policy_decision", "BLOCKED"),
                             ("policy_decision", "BLOCKED_NO_EFFECT"),
                             ("policy_decision", None),
                             ("stop_auto", True),
                             ("authenticated", False),
                             ("acl_ok", False),
                             ("human_answer_verified", False),
                             ("approval_specific", False)):
            with self.subTest(field=field):
                self.assertFalse(resume_admissible(replace(waiting(), **{field: value})))

    def test_live_is_never_admitted(self):
        self.assertFalse(resume_admissible(replace(
            waiting(), link=replace(LINK, mode="LIVE"), observed_mode="LIVE")))


if __name__ == "__main__":
    unittest.main()
