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

    def test_explicit_policy_denial_is_not_portal_defect_even_with_auth_reason(self):
        result = first_portal_hold(receipt([
            {"id": "blocked", "status": "HOLD", "owner": "portal",
             "reason": "auth_401", "policy_status": "DENIED"},
            {"id": "browser", "status": "HOLD", "owner": "browser",
             "reason": "legend_duplicate"}]), NOW)
        self.assertEqual(result["hold"]["id"], "browser")

    def test_hitl_pending_without_safe_reason_is_not_actionable(self):
        result = first_portal_hold(receipt([
            {"id": "waiting", "status": "HOLD", "component": "ui",
             "reason": "auth_401", "policy_state": " hitl_pending "}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIsNone(result["hold"])

    def test_cross_domain_component_cannot_be_attributed_to_portal(self):
        result = first_portal_hold(receipt([
            {"id": "core-auth", "status": "HOLD", "owner": "portal",
             "component": "core", "reason": "auth_401"},
            {"id": "worker", "status": "HOLD", "owner": "portal",
             "component": "worker", "reason": "timeout"},
            {"id": "browser", "status": "HOLD", "owner": "portal",
             "component": "browser", "reason": "legend_duplicate"}]), NOW)
        self.assertEqual(result["hold"]["id"], "browser")

    def test_only_cross_domain_components_fail_closed(self):
        result = first_portal_hold(receipt([
            {"id": "core", "status": "HOLD", "owner": "portal",
             "component": "core", "reason": "auth_401"}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIsNone(result["hold"])

    def test_pass_does_not_imply_live_success(self):
        result = first_portal_hold(receipt([{"status": "PASS", "owner": "portal"}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")


    def test_policy_component_with_portal_owner_is_not_portal_failure(self):
        result = first_portal_hold(receipt([
            {"id": "policy-fence", "status": "HOLD", "owner": "portal",
             "component": "policy", "reason": "auth_401"},
            {"id": "ui-defect", "status": "HOLD", "owner": "portal",
             "component": "browser", "reason": "legend_duplicate"}]), NOW)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["hold"]["id"], "ui-defect")

    def test_policy_only_mixed_labels_fail_closed(self):
        result = first_portal_hold(receipt([
            {"id": "hitl", "status": "HOLD", "owner": "portal",
             "component": "hitl", "reason": "auth_401"}]), NOW)
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIsNone(result["hold"])

if __name__ == "__main__":
    unittest.main()
