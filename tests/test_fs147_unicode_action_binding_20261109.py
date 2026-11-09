"""Regression: untrusted Unicode scope cannot crash HITL admission."""
import unittest
from datetime import datetime, timezone
from worker.fs147_action_binding import check_action_binding


class UnicodeActionBindingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 6, tzinfo=timezone.utc)
        self.intent = {
            "tenant_id": "tenant-1", "run_id": "run-1", "action_id": "action-1",
            "target": "fs-lab", "parameters_digest": "a" * 64,
            "policy_revision": "rev-1", "dry_run": True,
        }
        self.approval = {k: self.intent[k] for k in (
            "tenant_id", "run_id", "action_id", "target",
            "parameters_digest", "policy_revision"
        )}
        self.approval.update(
            decision="APPROVED", authenticated=True,
            issued_at="2026-11-09T06:00:00Z",
            expires_at="2026-11-09T06:10:00Z",
        )

    def check(self):
        return check_action_binding(self.intent, self.approval, now=self.now)

    def test_valid_ascii_stays_read_only(self):
        self.assertEqual(self.check()["status"], "BOUND_READ_ONLY")
        self.assertFalse(self.check()["dispatch_allowed"])

    def test_unicode_intent_is_unknown_not_exception(self):
        for key in ("tenant_id", "run_id", "action_id", "target", "policy_revision"):
            with self.subTest(key=key):
                original = self.intent[key]
                self.intent[key] = "é"
                result = self.check()
                self.assertEqual(result["reason"], "INVALID_INTENT")
                self.assertFalse(result["dispatch_allowed"])
                self.intent[key] = original

    def test_unicode_approval_is_unknown_not_exception(self):
        for key in ("tenant_id", "run_id", "action_id", "target", "policy_revision"):
            with self.subTest(key=key):
                original = self.approval[key]
                self.approval[key] = "é"
                result = self.check()
                self.assertEqual(result["reason"], "APPROVAL_MISMATCH")
                self.assertFalse(result["dispatch_allowed"])
                self.approval[key] = original

    def test_unicode_on_both_sides_still_denied(self):
        self.intent["target"] = self.approval["target"] = "é"
        self.assertEqual(self.check()["status"], "UNKNOWN")
        self.assertFalse(self.check()["dispatch_allowed"])


if __name__ == "__main__":
    unittest.main()
