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

    def test_run_identity_rejects_control_chars_and_non_ascii(self):
        # Prevent ambiguous identity joins across Core, Policy, Temporal and ITSM.
        for invalid in ("RUN-A B", "RUN-A\\nB", "RUN-A\\tB", "RUN-é", "RUN-ABC/DEF", "RUN-ABC.DEF", "RUN-_"):
            with self.subTest(invalid=invalid):
                r = receipt()
                r["run_id"] = invalid
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                self.assertEqual(r, before)

    def test_run_identity_accepts_canonical_ascii(self):
        r = receipt()
        r["run_id"] = "RUN-8CA56A39E58944F1"
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_explicit_cross_run_evidence_fails_closed(self):
        for check_name in sorted(REQUIRED):
            for bad_id in ("RUN-OTHER", None, ["RUN-TEST-001"]):
                with self.subTest(check=check_name, bad_id=bad_id):
                    r = receipt()
                    next(item for item in r["checks"] if item["name"] == check_name)["evidence"] = {"run_id": bad_id}
                    before = deepcopy(r)
                    self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                    self.assertEqual(r, before)

    def test_check_level_cross_run_attestation_fails_closed(self):
        for name in sorted(REQUIRED):
            for invalid in ("RUN-OTHER", None, ["RUN-TEST-001"], 0):
                with self.subTest(check=name, run_id=invalid):
                    r = receipt()
                    next(c for c in r["checks"] if c["name"] == name)["run_id"] = invalid
                    before = deepcopy(r)
                    self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                    self.assertEqual(r, before)

    def test_matching_check_level_run_attestation_remains_claim_only(self):
        r = receipt()
        for check in r["checks"]:
            check["run_id"] = r["run_id"]
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_matching_explicit_run_evidence_remains_claim_only(self):
        r = receipt()
        for item in r["checks"]:
            item["evidence"] = {"run_id": r["run_id"]}
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_hold_without_run_identity_is_unverified(self):
        r = receipt()
        r.pop("run_id")
        r["checks"][0]["status"] = "HOLD"
        r["blocking"] = [r["checks"][0]["name"]]
        r["verdict"] = "HOLD"
        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)

    def test_missing_report(self):
        self.assertEqual(classify(None, NOW), Qualification.UNVERIFIED)

    def test_invalid_freshness_threshold_never_upgrades_receipt(self):
        # NaN makes both age comparisons false without an explicit finite guard.
        for threshold in (float("nan"), float("inf"), float("-inf"), -1, None, True, "180"):
            with self.subTest(threshold=threshold):
                r = receipt()
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW + timedelta(days=1), threshold), Qualification.UNVERIFIED)
                self.assertEqual(r, before)

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

    def test_successful_probe_with_error_is_unverified(self):
        # A producer must not report both success and an execution failure.
        for name in ("platform", "linkage"):
            with self.subTest(name=name):
                r = receipt()
                r["probe_execution"][name]["error"] = "TIMEOUT"
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                self.assertEqual(r, before)

    def test_success_exit_with_timeout_or_cancellation_is_unverified(self):
        # An exit code alone cannot overrule an explicit execution abort.
        for probe_name in ("platform", "linkage"):
            for field in ("timed_out", "cancelled"):
                for value in (True, "true", 1):
                    with self.subTest(probe=probe_name, field=field, value=value):
                        r = receipt()
                        r["probe_execution"][probe_name][field] = value
                        before = deepcopy(r)
                        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                        self.assertEqual(r, before)

    def test_abort_flags_reject_false_equivalent_non_boolean_values(self):
        # Python equality treats 0 == False and "" == False is false, but
        # serialized probe flags must be explicit JSON booleans or null.
        for probe_name in ("platform", "linkage"):
            for field in ("timed_out", "cancelled"):
                for value in (0, 0.0, [], {}):
                    with self.subTest(probe=probe_name, field=field, value=value):
                        r = receipt()
                        r["probe_execution"][probe_name][field] = value
                        before = deepcopy(r)
                        self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                        self.assertEqual(r, before)

    def test_explicit_non_aborted_probes_remain_claim_only(self):
        r = receipt()
        for probe in r["probe_execution"].values():
            probe["timed_out"] = False
            probe["cancelled"] = False
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_probe_attestation_cannot_belong_to_another_run(self):
        for probe_name in ("platform", "linkage"):
            for invalid in ("RUN-OTHER", None, ["RUN-TEST-001"]):
                with self.subTest(probe=probe_name, run_id=invalid):
                    r = receipt()
                    r["probe_execution"][probe_name]["run_id"] = invalid
                    before = deepcopy(r)
                    self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                    self.assertEqual(r, before)

    def test_matching_probe_run_attestation_is_claim_only(self):
        r = receipt()
        for probe in r["probe_execution"].values():
            probe["run_id"] = r["run_id"]
        self.assertEqual(classify(r, NOW), Qualification.PASS_CLAIM_ONLY)

    def test_blocked_producer_evidence_without_run_binding_is_unverified(self):
        # The current producer's blocked-run evidence omits run_id.
        r = receipt()
        for item in r["checks"]:
            if item["name"] == "policy_denial_safety":
                item["evidence"] = {"run_status": "BLOCKED", "critic_policy_outbox": "PASS"}
            elif item["name"] in ("temporal_worker_history", "hitl_action_binding"):
                item["status"] = "NOT_APPLICABLE"
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

    def test_blocked_exemption_requires_actual_outbox_check_pass(self):
        # A nested claim cannot override a contradictory authoritative check.
        for status in ("HOLD", "UNVERIFIED"):
            with self.subTest(status=status):
                r = receipt()
                for check in r["checks"]:
                    if check["name"] == "policy_denial_safety":
                        check["evidence"] = {"run_id": r["run_id"], "run_status": "BLOCKED", "critic_policy_outbox": "PASS"}
                    elif check["name"] == "critic_policy_outbox":
                        check["status"] = status
                    elif check["name"] == "temporal_worker_history":
                        check["status"] = "NOT_APPLICABLE"
                if status == "HOLD":
                    r["blocking"] = ["critic_policy_outbox"]
                    r["verdict"] = "HOLD"
                before = deepcopy(r)
                self.assertEqual(classify(r, NOW), Qualification.UNVERIFIED)
                self.assertEqual(r, before)


if __name__ == "__main__":
    unittest.main()
