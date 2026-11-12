"""Regression: malformed correlation keys fail closed before Temporal dispatch.

Offline only: no GLPI writes, Temporal signals or filesystem mutations.
"""
from dataclasses import replace
import unittest

from app.core.fs364_dispatch_guard import DispatchState
from app.core.fs364_outbox_envelope import ResumeEnvelope, envelope_still_admissible


class CorrelationKeySafetyTests(unittest.TestCase):
    def test_control_and_whitespace_keys_are_rejected_on_both_sides(self):
        envelope = ResumeEnvelope(
            "alert:fs:92", "INC-DEMO-FS-001", "RUN-4FABD1786F107E51",
            "EVD-D2069BA816126499", "tenant-demo", "DEMO", 147,
            "fs364:resume:run:v1", "v1", "p1",
        )
        state = DispatchState(
            tenant_id="tenant-demo", run_id=envelope.run_id,
            mode="DEMO", ticket_id=147, state="WAITING_HUMAN",
            state_version="v1", policy_decision="ALLOW", policy_version="p1",
            stop_auto=False, human_answer_verified=True, approval_specific=True,
            approval_valid=True, glpi_verified=True, authenticated=True, acl_ok=True,
        )
        self.assertTrue(envelope_still_admissible(envelope, envelope, state, state))
        for field in ("alert_fingerprint", "incident_id", "run_id", "evidence_id",
                      "tenant_id", "idempotency_key", "state_version", "policy_version"):
            for bad in ("x y", "x\ty", "x\ny", "x\x00y", "x\u200by"):
                with self.subTest(field=field, bad=repr(bad)):
                    malformed = replace(envelope, **{field: bad})
                    self.assertFalse(envelope_still_admissible(malformed, envelope, state, state))
                    self.assertFalse(envelope_still_admissible(envelope, malformed, state, state))


if __name__ == "__main__":
    unittest.main()
