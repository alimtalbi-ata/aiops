"""Regression: explicit approval mode cannot be ambiguous or bypass dry-run binding."""
import unittest
from datetime import datetime, timezone, timedelta
from worker.fs147_action_binding import check_action_binding

NOW = datetime(2026, 11, 9, 17, 0, tzinfo=timezone.utc)

def fixtures():
    scope = dict(tenant_id="tenant-a", run_id="run-a", action_id="action-a",
                 target="fs-lab", parameters_digest="a"*64, policy_revision="policy-v1")
    intent = dict(scope, dry_run=True)
    approval = dict(scope, decision="APPROVED", authenticated=True,
                    issued_at=(NOW-timedelta(minutes=1)).isoformat(),
                    expires_at=(NOW+timedelta(minutes=1)).isoformat())
    return intent, approval

class ApprovalModeTests(unittest.TestCase):
    def test_legacy_absent_mode_remains_read_only(self):
        intent, approval = fixtures()
        self.assertEqual(check_action_binding(intent, approval, now=NOW)["status"], "BOUND_READ_ONLY")

    def test_valid_explicit_dry_run(self):
        intent, approval = fixtures()
        approval.update(mode="DRY_RUN", dry_run=True)
        result = check_action_binding(intent, approval, now=NOW)
        self.assertEqual(result["status"], "BOUND_READ_ONLY")
        self.assertFalse(result["dispatch_allowed"])

    def test_invalid_explicit_modes_fail_closed(self):
        for mode in ("LIVE", "REMEDIATE", "UNKNOWN", "", "dry_run", None, 1):
            with self.subTest(mode=mode):
                intent, approval = fixtures()
                approval["mode"] = mode
                result = check_action_binding(intent, approval, now=NOW)
                self.assertEqual(result["reason"], "APPROVAL_MODE_MISMATCH")
                self.assertFalse(result["dispatch_allowed"])

    def test_invalid_explicit_dry_run_flags_fail_closed(self):
        for flag in (False, "true", "false", 1, 0, None):
            with self.subTest(flag=flag):
                intent, approval = fixtures()
                approval["dry_run"] = flag
                result = check_action_binding(intent, approval, now=NOW)
                self.assertEqual(result["reason"], "APPROVAL_MODE_MISMATCH")
                self.assertFalse(result["dispatch_allowed"])

if __name__ == "__main__":
    unittest.main()
