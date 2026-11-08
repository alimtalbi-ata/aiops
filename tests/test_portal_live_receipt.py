import unittest
from datetime import datetime, timezone
from app.portal.live_receipt import portal_usecase_status

NOW = datetime(2026, 11, 8, 15, 46, tzinfo=timezone.utc)

class ReceiptTests(unittest.TestCase):
    def test_absent_is_unverified(self):
        self.assertEqual(portal_usecase_status(None, NOW)["status"], "UNVERIFIED")
    def test_stale_is_not_functional_failure(self):
        self.assertEqual(portal_usecase_status({"collected_at":"2026-11-08T15:40:00Z","checks":[{"status":"HOLD"}]}, NOW)["status"], "STALE")
    def test_hold_is_preserved(self):
        result = portal_usecase_status({"collected_at":"2026-11-08T15:45:00Z","checks":[{"id":"portal-auth","status":"HOLD","reason":"unauthorized"}]}, NOW)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["holds"][0]["id"], "portal-auth")
    def test_empty_checks_cannot_pass(self):
        self.assertEqual(portal_usecase_status({"collected_at":"2026-11-08T15:45:00Z","checks":[]}, NOW)["status"], "UNVERIFIED")
    def test_future_is_unverified(self):
        self.assertEqual(portal_usecase_status({"collected_at":"2026-11-08T16:00:00Z","checks":[]}, NOW)["reason"], "timestamp_future")

if __name__ == "__main__":
    unittest.main()
