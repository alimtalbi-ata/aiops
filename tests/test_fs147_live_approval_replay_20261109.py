"""Fail-closed when a live Policy approval is replayed for a dry-run action."""
import unittest
from datetime import datetime, timezone
from worker.fs147_action_binding import check_action_binding


class ApprovalModeReplayTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 6, tzinfo=timezone.utc)
        self.intent = {
            "tenant_id": "tenant-1", "run_id": "run-1", "action_id": "action-1",
            "target": "fs-lab", "parameters_digest": "a" * 64,
            "policy_revision": "rev-1", "dry_run": True,
        }
        self.approval = {key: self.intent[key] for key in (
            "tenant_id", "run_id", "action_id", "target",
            "parameters_digest", "policy_revision"
        )}
        self.approval.update(
            decision="APPROVED", authenticated=True,
            issued_at="2026-11-09T06:00:00Z",
            expires_at="2026-11-09T06:10:00Z",
        )

    def evaluate(self):
        return check_action_binding(self.intent, self.approval, now=self.now)

    def test_explicit_live_boolean_denied(self):
        self.approval["dry_run"] = False
        result = self.evaluate()
        self.assertEqual(result["reason"], "APPROVAL_MODE_MISMATCH")
        self.assertFalse(result["dispatch_allowed"])

    def test_explicit_live_mode_denied(self):
        for mode in ("LIVE", "REMEDIATE"):
            with self.subTest(mode=mode):
                self.approval["mode"] = mode
                result = self.evaluate()
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertFalse(result["dispatch_allowed"])

    def test_explicit_dry_run_stays_read_only(self):
        self.approval.update(dry_run=True, mode="DEMO")
        result = self.evaluate()
        self.assertEqual(result["status"], "BOUND_READ_ONLY")
        self.assertFalse(result["dispatch_allowed"])


if __name__ == "__main__":
    unittest.main()
