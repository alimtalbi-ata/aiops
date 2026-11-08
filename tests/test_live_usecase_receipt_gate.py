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
        "run_id": "RUN-TEST-001",
        "verdict": "PASS",
        "checks": [{"name": name, "status": "PASS"} for name in sorted(REQUIRED)],
        "blocking": [],
        "probe_execution": {"platform": {"exit": 0}, "linkage": {"exit": 0}},
    }


class ReceiptTests(unittest.TestCase):
    def test_complete_claim_is_not_authorization(self):
        self.assertEqual(classify(receipt(), NOW), Qualification.PASS_CLAIM_ONLY)

    def test_all_pass_without_canonical_run_is_unverified(self):
        for invalid in (None, "", " ", "TEST-001", "RUN-", " RUN-001", "RUN-001 ", 123, ["RUN-001"], "RUN-" + "X" * 82):
            with self.subTest(invalid=invalid):
                r = receipt()
                r["run_id"] = invalid
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                self.assertEqual(r, before)

    def test_hold_without_run_identity_is_unverified(self):
        r = receipt()
        r.pop("run_id")
        r["checks"][0]["status"] = "HOLD"
        r["blocking"] = [r["checks"][0]["name"]]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

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
            if c["name"] == "policy_denial_safety":
                c["evidence"] = {"run_id": r["run_id"], "run_status": "BLOCKED", "critic_policy_outbox": "PASS"}
            if c["name"] in ("hitl_action_binding", "temporal_worker_history"):
                c["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_not_applicable_without_blocked_run_evidence_is_unverified(self):
        r = receipt()
        for check in r["checks"]:
            if check["name"] == "temporal_worker_history":
                check["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_not_applicable_rejects_unrelated_safety_evidence(self):
        r = receipt()
        for check in r["checks"]:
            if check["name"] == "policy_denial_safety":
                check["evidence"] = {"run_status": "RUNNING", "critic_policy_outbox": "PASS"}
            if check["name"] == "hitl_action_binding":
                check["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_not_applicable_rejects_unverified_outbox(self):
        r = receipt()
        for check in r["checks"]:
            if check["name"] == "policy_denial_safety":
                check["evidence"] = {"run_status": "BLOCKED", "critic_policy_outbox": "UNKNOWN"}
            if check["name"] == "temporal_worker_history":
                check["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_not_applicable_rejects_unbound_or_other_run(self):
        for other_run in (None, "RUN-OTHER"):
            with self.subTest(other_run=other_run):
                r = receipt()
                for check in r["checks"]:
                    if check["name"] == "policy_denial_safety":
                        check["evidence"] = {"run_id": other_run, "run_status": "BLOCKED", "critic_policy_outbox": "PASS"}
                    if check["name"] == "temporal_worker_history":
                        check["status"] = "NOT_APPLICABLE"
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_not_applicable_requires_receipt_run_id(self):
        r = receipt()
        del r["run_id"]
        for check in r["checks"]:
            if check["name"] == "policy_denial_safety":
                check["evidence"] = {"run_id": "RUN-TEST-001", "run_status": "BLOCKED", "critic_policy_outbox": "PASS"}
            if check["name"] == "hitl_action_binding":
                check["status"] = "NOT_APPLICABLE"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

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

    def test_missing_evidence_is_not_functional_hold(self):
        r = receipt()
        r["checks"][0]["status"] = "UNVERIFIED"
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_mixed_hold_and_missing_evidence_stays_unverified(self):
        r = receipt()
        r["checks"][0]["status"] = "UNVERIFIED"
        r["checks"][1]["status"] = "HOLD"
        r["blocking"] = [r["checks"][1]["name"]]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_actual_hold_remains_hold(self):
        r = receipt()
        r["checks"][0]["status"] = "HOLD"
        r["blocking"] = [r["checks"][0]["name"]]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.HOLD)

    def test_malformed_blocking_entries_fail_closed(self):
        for malformed in ([{"name": "core_run_consistency"}], [["core_run_consistency"]], [None], [1], [True]):
            with self.subTest(malformed=malformed):
                r = receipt()
                r["checks"][0]["status"] = "HOLD"
                r["verdict"] = "HOLD"
                r["blocking"] = malformed
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                self.assertEqual(r, before)

    def test_duplicate_blocking_entries_fail_closed(self):
        r = receipt()
        r["checks"][0]["status"] = "HOLD"
        r["verdict"] = "HOLD"
        r["blocking"] = [r["checks"][0]["name"]] * 2
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_live_mutation_receipt(self):
        r = receipt()
        r["read_only"] = False
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
