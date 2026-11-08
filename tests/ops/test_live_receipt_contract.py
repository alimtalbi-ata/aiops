"""Offline fail-closed contract for the published Debian live-usecase receipt.

This is an integration contract test, not a Debian E2E test.
"""
import unittest


def verdict(receipt):
    if not isinstance(receipt, dict) or receipt.get("schema") != "aiops2-live-usecase-qualification-v1":
        return "UNVERIFIED"
    if receipt.get("read_only") is not True or not receipt.get("utc"):
        return "UNVERIFIED"
    checks = receipt.get("checks")
    if not isinstance(checks, list) or not checks:
        return "UNVERIFIED"
    for check in checks:
        if not isinstance(check, dict) or not check.get("name") or check.get("status") not in ("PASS", "HOLD", "UNVERIFIED", "NOT_APPLICABLE"):
            return "UNVERIFIED"
    if receipt.get("verdict") != "PASS" or receipt.get("blocking") or any(c["status"] in ("HOLD", "UNVERIFIED") for c in checks):
        return "HOLD"
    if any(c["status"] == "NOT_APPLICABLE" for c in checks):
        return "UNVERIFIED"
    return "PASS"


class ReceiptContract(unittest.TestCase):
    def setUp(self):
        self.receipt = {"schema": "aiops2-live-usecase-qualification-v1", "utc": "2026-11-08T20:00:00+00:00", "read_only": True, "verdict": "PASS", "blocking": [], "checks": [{"name": "platform_smoke", "status": "PASS", "evidence": {}, "next_action": None}]}

    def test_pass(self):
        self.assertEqual(verdict(self.receipt), "PASS")

    def test_hold_cannot_be_pass(self):
        self.receipt["checks"][0]["status"] = "HOLD"
        self.assertEqual(verdict(self.receipt), "HOLD")

    def test_missing_provenance_is_unverified(self):
        for key in ("schema", "utc", "read_only", "checks"):
            with self.subTest(key=key):
                candidate = dict(self.receipt)
                candidate.pop(key)
                self.assertEqual(verdict(candidate), "UNVERIFIED")

    def test_missing_check_identity_is_unverified(self):
        self.receipt["checks"] = [{"status": "PASS"}]
        self.assertEqual(verdict(self.receipt), "UNVERIFIED")

    def test_safe_denial_not_execution_proof(self):
        self.receipt["checks"] = [{"name": "hitl_action_binding", "status": "NOT_APPLICABLE"}]
        self.assertEqual(verdict(self.receipt), "UNVERIFIED")

    def test_unverified_check_cannot_be_pass(self):
        self.receipt["checks"][0]["status"] = "UNVERIFIED"
        self.assertEqual(verdict(self.receipt), "HOLD")


if __name__ == "__main__":
    unittest.main()
