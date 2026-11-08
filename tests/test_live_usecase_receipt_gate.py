"""Offline regression tests for the read-only Debian receipt contract."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from app.core.live_usecase_receipt_gate import classify, Qualification, REQUIRED


NOW = datetime(2026, 11, 8, 16, 10, tzinfo=timezone.utc)


def receipt():
    return {
        "schema": "aiops2-live-usecase-qualification-v1",
        "utc": "2026-11-08T16:09:00+00:00",
        "read_only": True,
        "verdict": "PASS",
        "checks": [{"name": name, "status": "PASS"} for name in sorted(REQUIRED)],
        "blocking": [],
        "probe_execution": {"platform": {"exit": 0}, "linkage": {"exit": 0}},
    }


class ReceiptTests(unittest.TestCase):
    def test_complete_claim_is_not_authorization(self):
        self.assertEqual(classify(receipt(), NOW), Qualification.PASS_CLAIM_ONLY)

    def test_missing_report(self):
        self.assertEqual(classify(None, NOW), Qualification.UNVERIFIED)

    def test_stale(self):
        self.assertEqual(classify(receipt(), NOW + timedelta(minutes=5)), Qualification.UNVERIFIED)

    def test_missing_check(self):
        r = receipt()
        r["checks"].pop()
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_duplicate_check(self):
        r = receipt()
        r["checks"][1] = deepcopy(r["checks"][0])
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_probe_not_executed(self):
        r = receipt()
        r["probe_execution"]["linkage"]["exit"] = 127
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_hold_not_success(self):
        r = receipt()
        r["checks"][0]["status"] = "HOLD"
        r["blocking"] = [r["checks"][0]["name"]]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.HOLD)

    def test_blocked_action_not_applicable(self):
        r = receipt()
        for c in r["checks"]:
            if c["name"] in ("hitl_action_binding", "temporal_worker_history"):
                c["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_unjustified_not_applicable(self):
        r = receipt()
        for c in r["checks"]:
            if c["name"] == "hitl_action_binding":
                c["status"] = "NOT_APPLICABLE"
            if c["name"] == "policy_denial_safety":
                c["status"] = "HOLD"
        r["blocking"] = ["policy_denial_safety"]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_live_mutation_receipt(self):
        r = receipt()
        r["read_only"] = False
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
