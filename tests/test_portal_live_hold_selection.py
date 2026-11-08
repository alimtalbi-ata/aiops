"""Offline contract tests; synthetic receipts are not Debian E2E evidence."""
import unittest
from datetime import datetime, timezone, timedelta
from app.portal.live_hold_selection import first_portal_hold


NOW = datetime(2026, 11, 8, 16, 45, tzinfo=timezone.utc)


def receipt(checks, at=NOW):
    return {"collected_at": at.isoformat(), "checks": checks}


class LiveHoldSelectionTests(unittest.TestCase):
    def test_missing_receipt_is_unverified(self):
        self.assertEqual(first_portal_hold(None, NOW)["status"], "UNVERIFIED")

    def test_stale_receipt_is_not_a_failure(self):
        result = first_portal_hold(receipt([{"status": "HOLD", "owner": "portal"}],
                                           NOW - timedelta(minutes=4)), NOW)
        self.assertEqual(result["status"], "STALE")
        self.assertIsNone(result["hold"])

    def test_first_portal_hold_not_other_domains(self):
        result = first_portal_hold(receipt([
            {"id": "core-1", "status": "HOLD", "owner": "core"},
            {"id": "portal-1", "status": "HOLD", "owner": "portal", "reason": "auth_401"},
            {"id": "portal-2", "status": "HOLD", "owner": "portal"}]), NOW)
        self.assertEqual(result["hold"]["id"], "portal-1")

    def test_policy_denial_is_not_portal_defect(self):
        result = first_portal_hold(receipt([
            {"id": "p", "status": "HOLD", "owner": "portal", "reason": "hitl_pending"}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIsNone(result["hold"])

    def test_pass_does_not_imply_live_success(self):
        result = first_portal_hold(receipt([{"status": "PASS", "owner": "portal"}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
