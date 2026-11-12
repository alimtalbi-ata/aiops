"""Offline FS.364 outbox validation tests: no GLPI/Temporal I/O."""
from dataclasses import replace
import unittest

from app.core.fs364_dispatch_guard import DispatchState
from app.core.fs364_outbox_envelope import ResumeEnvelope, envelope_still_admissible


class OutboxEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.envelope = ResumeEnvelope(
            "alert:fs:92", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
            "EVD-D2069BA816126499", "tenant-demo", "DEMO", 147,
            "fs364:resume:run:v1", "v1", "p1",
        )
        self.state = DispatchState(
            tenant_id="tenant-demo", run_id=self.envelope.run_id,
            mode="DEMO", ticket_id=147, state="WAITING_HUMAN",
            state_version="v1", policy_decision="ALLOW", policy_version="p1",
            stop_auto=False, human_answer_verified=True, approval_specific=True,
            approval_valid=True, glpi_verified=True, authenticated=True, acl_ok=True,
        )

    def check(self, envelope=None, state=None):
        return envelope_still_admissible(
            self.envelope, envelope if envelope is not None else self.envelope,
            self.state, state if state is not None else self.state,
        )

    def test_exact_replay_is_pure_and_admissible(self):
        self.assertTrue(self.check())
        self.assertTrue(self.check())

    def test_all_correlation_identity_drifts_rejected(self):
        for name in ("alert_fingerprint", "incident_id", "run_id", "evidence_id",
                     "tenant_id", "idempotency_key", "state_version", "policy_version"):
            with self.subTest(field=name):
                self.assertFalse(self.check(envelope=replace(self.envelope, **{name: "changed"})))

    def test_wrong_ticket_live_and_bad_types_rejected(self):
        for patch in ({"ticket_id": 146}, {"ticket_id": True},
                      {"mode": "LIVE"}, {"evidence_id": ""}, {"tenant_id": " x "}):
            with self.subTest(patch=patch):
                self.assertFalse(self.check(envelope=replace(self.envelope, **patch)))

    def test_revocation_and_state_mismatch_rejected(self):
        for patch in ({"policy_decision": "BLOCKED"}, {"stop_auto": True},
                      {"state": "BLOCKED_NO_EFFECT"}, {"approval_valid": False},
                      {"glpi_verified": False}, {"state_version": "v2"},
                      {"policy_version": "p2"}, {"run_id": "other"}):
            with self.subTest(patch=patch):
                self.assertFalse(self.check(state=replace(self.state, **patch)))

    def test_bad_admission_snapshot_rejected(self):
        self.assertFalse(envelope_still_admissible(
            self.envelope, self.envelope,
            replace(self.state, policy_decision="BLOCKED"), self.state,
        ))


if __name__ == "__main__":
    unittest.main()
