"""Offline, no GLPI/Temporal/DB side effects."""
import unittest
from dataclasses import replace

from app.core.fs364_dispatch_boundary import dispatch_boundary_ok
from app.core.fs364_outbox_envelope import ResumeEnvelope
from app.core.fs364_dispatch_guard import DispatchState
from app.core.fs364_outbox_transition import OutboxRecord


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.envelope = ResumeEnvelope(
            "fingerprint", "incident", "run", "evidence", "tenant",
            "DEMO", 147, "idem", "v1", "p1")
        self.state = DispatchState(
            "tenant", "run", "DEMO", 147, "WAITING_HUMAN", "v1",
            "ALLOW", "p1", False, True, True, True, True, True, True)
        self.record = OutboxRecord(
            "event", 2, "CLAIMED", 1, "tenant", "idem", 147, "DEMO")

    def check(self, record=None, admitted=None, current=None,
              admitted_state=None, current_state=None, **flags):
        return dispatch_boundary_ok(
            self.record if record is None else record,
            self.envelope if admitted is None else admitted,
            self.envelope if current is None else current,
            self.state if admitted_state is None else admitted_state,
            self.state if current_state is None else current_state,
            expected_revision=flags.pop("expected_revision", 2),
            authoritative_read=flags.pop("authoritative_read", True),
            lease_owned=flags.pop("lease_owned", True), **flags)

    def test_valid_demo_is_repeatable_without_mutation(self):
        before = (self.record, self.envelope, self.state)
        self.assertTrue(self.check())
        self.assertTrue(self.check())
        self.assertEqual(before, (self.record, self.envelope, self.state))

    def test_outbox_lease_and_authority_fail_closed(self):
        for changes in (
            {"record": replace(self.record, status="PENDING")},
            {"record": replace(self.record, mode="LIVE")},
            {"record": replace(self.record, ticket_id=146)},
            {"record": replace(self.record, tenant_id="other")},
            {"record": replace(self.record, idempotency_key="other")},
            {"record": replace(self.record, attempt=0)},
            {"expected_revision": 1},
            {"expected_revision": True},
            {"authoritative_read": False},
            {"authoritative_read": 1},
            {"lease_owned": False},
            {"lease_owned": 1},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.check(**changes))

    def test_policy_revoke_and_resume_identity(self):
        for changes in (
            {"current_state": replace(self.state, policy_decision="DENY")},
            {"current_state": replace(self.state, stop_auto=True)},
            {"current_state": replace(self.state, human_answer_verified=False)},
            {"current_state": replace(self.state, approval_specific=False)},
            {"current_state": replace(self.state, approval_valid=False)},
            {"current_state": replace(self.state, glpi_verified=False)},
            {"current_state": replace(self.state, authenticated=False)},
            {"current_state": replace(self.state, acl_ok=False)},
            {"current_state": replace(self.state, state_version="v2")},
            {"current": replace(self.envelope, evidence_id="other")},
            {"current": replace(self.envelope, mode="LIVE")},
            {"admitted_state": replace(self.state, policy_decision="DENY")},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.check(**changes))


if __name__ == "__main__":
    unittest.main()
