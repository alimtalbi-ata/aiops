"""FS.364 offline regression: admission and dispatch are both fail-closed.

No GLPI, database, Temporal or LIVE side effects.
"""
from dataclasses import replace
import unittest

from app.core.fs364_dispatch_guard import DispatchState, dispatch_still_admissible
from app.core.fs364_outbox_envelope import ResumeEnvelope, envelope_still_admissible


class FS364RevalidationBoundary(unittest.TestCase):
    def setUp(self):
        self.env = ResumeEnvelope(
            "alert:fs:92", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
            "EVD-D2069BA816126499", "tenant-demo", "DEMO", 147,
            "fs364:resume:run:v1", "v1", "p1")
        self.state = DispatchState(
            tenant_id="tenant-demo", run_id=self.env.run_id, mode="DEMO",
            ticket_id=147, state="WAITING_HUMAN", state_version="v1",
            policy_decision="ALLOW", policy_version="p1", stop_auto=False,
            human_answer_verified=True, approval_specific=True,
            approval_valid=True, glpi_verified=True, authenticated=True,
            acl_ok=True)

    def test_exact_replay_has_no_mutation(self):
        before = (repr(self.env), repr(self.state))
        for _ in range(3):
            self.assertTrue(envelope_still_admissible(
                self.env, self.env, self.state, self.state))
        self.assertEqual(before, (repr(self.env), repr(self.state)))

    def test_revoked_admission_cannot_be_repaired_by_current_allow(self):
        for change in (
            {"policy_decision": "BLOCKED"}, {"state": "BLOCKED_NO_EFFECT"},
            {"glpi_verified": False}, {"approval_valid": False},
            {"human_answer_verified": False}, {"stop_auto": True},
            {"authenticated": False}, {"acl_ok": False},
        ):
            with self.subTest(change=change):
                self.assertFalse(envelope_still_admissible(
                    self.env, self.env, replace(self.state, **change), self.state))

    def test_same_key_different_evidence_or_incident_is_conflict(self):
        for change in ({"evidence_id": "EVD-OTHER"},
                       {"incident_id": "INC-OTHER"},
                       {"alert_fingerprint": "alert:other"}):
            with self.subTest(change=change):
                self.assertFalse(envelope_still_admissible(
                    self.env, replace(self.env, **change),
                    self.state, self.state))

    def test_no_ticket_146_or_live_even_with_valid_policy(self):
        for change in ({"ticket_id": 146}, {"mode": "LIVE"}):
            with self.subTest(change=change):
                self.assertFalse(dispatch_still_admissible(
                    self.state, replace(self.state, **change)))
                self.assertFalse(envelope_still_admissible(
                    self.env, replace(self.env, **change),
                    self.state, self.state))


if __name__ == "__main__":
    unittest.main()
