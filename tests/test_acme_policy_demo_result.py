"""No-effect presentation contract tests; no Core, GLPI or Temporal I/O."""
import copy
import hashlib
import json
import unittest

from app.shared.acme_policy_demo_result import present_demo_policy_result


def receipt(status="SIMULATED_SUCCESS", gate_status="SIMULATED"):
    before = {"target_ci": "ACME-LNX-01", "health": "DEGRADED", "service_available": False}
    after = {"target_ci": "ACME-LNX-01", "health": "HEALTHY", "service_available": True} if status == "SIMULATED_SUCCESS" else dict(before)
    binding = {
        "run_id": "RUN-ACME-OFFLINE-001", "scenario_id": "SCN-ACME-OFFLINE",
        "mode": "DEMO", "proposal_digest": "b" * 64,
        "evidence_ids": ["EVD-ACME-OFFLINE-1"],
        "outcome": "FAILURE" if status == "SIMULATED_FAILURE" else "SUCCESS",
    }
    digest = hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    idempotency_key = hashlib.sha256(json.dumps(
        {"proposal_digest": "b" * 64, "executor": "NO_EFFECT_SIMULATOR"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()).hexdigest()
    return {
        "schema": "aiops.acme-remediation-receipt.v1", "classification": "SYNTHETIC_UNVERIFIED",
        "run_id": "RUN-ACME-OFFLINE-001", "scenario_id": "SCN-ACME-OFFLINE",
        "evidence_ids": ["EVD-ACME-OFFLINE-1"], "receipt_digest": digest,
        "core_run_verified": False, "evidence_verified": False, "effect_applied": False, "persisted": False,
        "projection": {
            "schema_version": 1, "synthetic": True, "provenance": "WHAT_IF_FIXTURE_NOT_OBSERVED",
            "mode": "DEMO", "status": status, "recipe_id": "ansible-service-restart",
            "reason": {
                "SIMULATED_SUCCESS": "HYPOTHETICAL_RECOVERY_NOT_VERIFIED",
                "SIMULATED_FAILURE": "HYPOTHETICAL_POSTCONDITION_FAILURE",
                "SIMULATED_NO_RECOVERY": "RECIPE_NOT_RECOVERY_CAPABLE",
            }.get(status, "APPROVAL_EXPIRED"),
            "target_ci": "ACME-LNX-01", "proposal_digest": "b" * 64,
            "idempotency_key": idempotency_key,
            "effect_applied": False, "postchecks": "NOT_RUN", "before": before, "after": after,
            "rollback": {
                "status": {
                    "SIMULATED_SUCCESS": "AVAILABLE_AS_PROJECTION",
                    "SIMULATED_FAILURE": "PROJECTED_ONLY",
                    "SIMULATED_NO_RECOVERY": "NOT_REQUIRED",
                    "BLOCKED": "NOT_REQUIRED",
                }.get(status, "NOT_REQUIRED"),
                "effect_applied": False,
            },
            "gate": {
                "mode": "DEMO", "status": gate_status, "target_ci": "ACME-LNX-01",
                "reason": "NO_SIDE_EFFECTS" if gate_status == "SIMULATED" else "APPROVAL_EXPIRED",
                "proposal_digest": "b" * 64, "recipe_id": "ansible-service-restart",
                "recipe_version": "1.0.0",
                "idempotency_key": idempotency_key, "executor": "NO_EFFECT_SIMULATOR",
                "effect_applied": False, "postchecks": "NOT_RUN", "rollback": "NOT_REQUIRED",
                "dry_run": True, "preconditions": "FIXTURE_ASSERTED_NOT_RUNTIME_VERIFIED",
                "approval_actor": "approver-fixture",
            },
        },
    }


class PolicyDemoResultTests(unittest.TestCase):
    def test_simulate_is_explicitly_not_authenticated_or_executed(self):
        result = present_demo_policy_result(receipt())
        self.assertEqual(result["policy"]["decision"], "SIMULATE")
        self.assertEqual(result["human"]["status"], "APPROVAL_FIXTURE_ONLY")
        self.assertFalse(result["human"]["authenticated_runtime"])
        self.assertFalse(result["effect_applied"])
        self.assertFalse(result["evidence"]["core_verified"])
        self.assertFalse(result["before_after"]["observed"])
        self.assertEqual(result["before_after"]["after_hypothesis"]["health"], "HEALTHY")
        self.assertTrue(result["rollback"]["projected_only"])

    def test_blocked_is_not_simulate(self):
        result = present_demo_policy_result(receipt("BLOCKED", "BLOCKED"))
        self.assertEqual(result["policy"]["decision"], "BLOCKED")
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertEqual(result["before_after"]["before"], result["before_after"]["after_hypothesis"])

    def test_failure_is_hypothetical(self):
        result = present_demo_policy_result(receipt("SIMULATED_FAILURE"))
        self.assertEqual(result["policy"]["decision"], "SIMULATE")
        self.assertFalse(result["effect_applied"])

    def test_live_mode_rejected(self):
        r = receipt(); r["projection"]["mode"] = "LIVE"; r["projection"]["gate"]["mode"] = "LIVE"
        with self.assertRaisesRegex(ValueError, "mode_not_demo"):
            present_demo_policy_result(r)

    def test_false_attestation_rejected(self):
        for key in ("core_run_verified", "evidence_verified", "effect_applied", "persisted"):
            with self.subTest(key=key):
                r = receipt(); r[key] = True
                with self.assertRaisesRegex(ValueError, "receipt_attestation_claim_forbidden"):
                    present_demo_policy_result(r)

    def test_forged_gate_success_rejected(self):
        with self.assertRaisesRegex(ValueError, "projection_gate_inconsistent"):
            present_demo_policy_result(receipt("SIMULATED_SUCCESS", "BLOCKED"))

    def test_snapshot_target_mismatch_rejected(self):
        r = receipt(); r["projection"]["after"]["target_ci"] = "ACME-SAN-FABRIC-A"
        with self.assertRaisesRegex(ValueError, "snapshot_binding_invalid"):
            present_demo_policy_result(r)

    def test_rollback_execution_claim_rejected(self):
        r = receipt(); r["projection"]["rollback"]["effect_applied"] = True
        with self.assertRaisesRegex(ValueError, "rollback_effect_claim_forbidden"):
            present_demo_policy_result(r)

    def test_forged_projection_provenance_rejected(self):
        for key, value in (("synthetic", False), ("provenance", "OBSERVED")):
            with self.subTest(key=key):
                r = receipt(); r["projection"][key] = value
                with self.assertRaisesRegex(ValueError, "projection_provenance_invalid"):
                    present_demo_policy_result(r)

    def test_forged_rollback_status_or_state_rejected(self):
        for key, value in (
            ("status", "EXECUTED"), ("executed", True),
            ("projected_state", {"target_ci": "ACME-LNX-01", "health": "HEALTHY", "service_available": True}),
        ):
            with self.subTest(key=key):
                r = receipt(); r["projection"]["rollback"][key] = value
                with self.assertRaisesRegex(ValueError, "rollback_effect_claim_forbidden"):
                    present_demo_policy_result(r)

    def test_real_receipt_builder_success_and_failure(self):
        """Exercise the existing receipt -> projection -> local gate -> presentation chain."""
        from app.shared.acme_demo_offline import demo_receipt

        for outcome, expected in (("SUCCESS", "SIMULATED_SUCCESS"), ("FAILURE", "SIMULATED_FAILURE")):
            with self.subTest(outcome=outcome):
                source = demo_receipt(outcome)
                self.assertEqual(source["projection"]["status"], expected)
                result = present_demo_policy_result(source)
                self.assertEqual(result["policy"]["decision"], "SIMULATE")
                self.assertEqual(result["classification"], "SIMULATED")
                self.assertEqual(result["run_id"], source["run_id"])
                self.assertEqual(result["evidence"]["ids"], source["evidence_ids"])
                self.assertEqual(result["evidence"]["receipt_digest"], source["receipt_digest"])
                self.assertEqual(result["human"]["status"], "APPROVAL_FIXTURE_ONLY")
                self.assertFalse(result["human"]["authenticated_runtime"])
                self.assertFalse(result["policy"]["core_policy_verified"])
                self.assertFalse(result["before_after"]["observed"])
                self.assertFalse(result["rollback"]["executed"])
                self.assertFalse(result["effect_applied"])
                self.assertFalse(result["persisted"])

    def test_real_receipt_builder_blocked_decision_not_approved(self):
        """The receipt builder must not be bypassed by a forged approved-looking fixture."""
        from app.shared.acme_demo_offline import demo_receipt

        source = demo_receipt("SUCCESS")
        source["projection"]["gate"]["status"] = "BLOCKED"
        with self.assertRaisesRegex(ValueError, "projection_gate_inconsistent"):
            present_demo_policy_result(source)

    def test_forged_no_effect_gate_rejected(self):
        for key, value in (
            ("executor", "LIVE_EXECUTOR"), ("effect_applied", True),
            ("postchecks", "PASS"), ("rollback", "EXECUTED"),
        ):
            with self.subTest(key=key):
                r = receipt(); r["projection"]["gate"][key] = value
                with self.assertRaisesRegex(ValueError, "gate_no_effect_contract_invalid"):
                    present_demo_policy_result(r)

    def test_gate_recipe_and_idempotency_binding_rejected(self):
        for key, value in (("recipe_id", "glpi-api-ticket-note"), ("idempotency_key", "f" * 64)):
            with self.subTest(key=key):
                r = receipt(); r["projection"]["gate"][key] = value
                with self.assertRaisesRegex(ValueError, "gate_binding_invalid"):
                    present_demo_policy_result(r)

    def test_fixture_permission_and_dry_run_fail_closed(self):
        for key, value in (("dry_run", False), ("preconditions", "RUNTIME_VERIFIED"), ("approval_actor", None)):
            with self.subTest(key=key):
                r = receipt(); r["projection"]["gate"][key] = value
                with self.assertRaisesRegex(ValueError, "gate_fixture_invalid"):
                    present_demo_policy_result(r)

    def test_permissions_audit_and_expiry_never_attested(self):
        for r in (receipt(), receipt("BLOCKED", "BLOCKED")):
            result = present_demo_policy_result(r)
            self.assertFalse(result["permissions"]["rbac_verified"])
            self.assertFalse(result["permissions"]["tenant_acl_qualified"])
            self.assertFalse(result["permissions"]["action_allowed"])
            self.assertFalse(result["permissions"]["separation_of_duties_runtime_verified"])
            self.assertFalse(result["human"]["approval_valid_now"])
            self.assertFalse(result["human"]["approval_expiry_verified"])
            self.assertFalse(result["audit"]["persisted"])
            self.assertFalse(result["audit"]["runtime_verified"])
            self.assertIsNone(result["audit"]["observed_at"])
            self.assertEqual(result["audit"]["receipt_digest"], r["receipt_digest"])
            self.assertEqual(result["audit"]["proposal_digest"], r["projection"]["proposal_digest"])

    def test_snapshot_schema_and_types_fail_closed(self):
        for snapshot, key, value in (
            ("before", "health", "RECOVERED"),
            ("after", "service_available", "yes"),
            ("before", "unexpected", True),
        ):
            with self.subTest(snapshot=snapshot, key=key):
                r = receipt()
                r["projection"][snapshot][key] = value
                with self.assertRaisesRegex(ValueError, "snapshot_schema_invalid"):
                    present_demo_policy_result(r)

    def test_forged_success_after_hypothesis_rejected(self):
        for key, value in (("health", "FAILED"), ("service_available", False)):
            with self.subTest(key=key):
                r = receipt()
                r["projection"]["after"][key] = value
                with self.assertRaisesRegex(ValueError, "projection_outcome_inconsistent"):
                    present_demo_policy_result(r)

    def test_failure_blocked_or_no_recovery_cannot_claim_recovery(self):
        for status, gate_status in (
            ("SIMULATED_FAILURE", "SIMULATED"),
            ("SIMULATED_NO_RECOVERY", "SIMULATED"),
            ("BLOCKED", "BLOCKED"),
        ):
            with self.subTest(status=status):
                r = receipt(status, gate_status)
                r["projection"]["after"]["health"] = "HEALTHY"
                with self.assertRaisesRegex(ValueError, "projection_outcome_inconsistent"):
                    present_demo_policy_result(r)

    def test_rollback_status_must_match_hypothetical_outcome(self):
        for status, gate_status, forged in (
            ("SIMULATED_SUCCESS", "SIMULATED", "PROJECTED_ONLY"),
            ("SIMULATED_FAILURE", "SIMULATED", "AVAILABLE_AS_PROJECTION"),
            ("SIMULATED_NO_RECOVERY", "SIMULATED", "PROJECTED_ONLY"),
            ("BLOCKED", "BLOCKED", "PROJECTED_ONLY"),
        ):
            with self.subTest(status=status):
                r = receipt(status, gate_status)
                r["projection"]["rollback"]["status"] = forged
                with self.assertRaisesRegex(ValueError, "projection_outcome_inconsistent"):
                    present_demo_policy_result(r)

    def test_receipt_binding_tampering_fail_closed(self):
        for path, forged in (
            ("run_id", "RUN-OTHER"),
            ("scenario_id", "SCN-OTHER"),
            ("evidence_ids", ["EVD-OTHER"]),
            ("receipt_digest", "f" * 64),
        ):
            with self.subTest(path=path):
                r = receipt()
                r[path] = forged
                with self.assertRaisesRegex(ValueError, "receipt_binding_digest_mismatch"):
                    present_demo_policy_result(r)

    def test_receipt_mode_and_proposal_digest_tampering_fail_closed(self):
        for path, forged in (("mode", "REPLAY"), ("proposal_digest", "d" * 64)):
            with self.subTest(path=path):
                r = receipt()
                r["projection"][path] = forged
                r["projection"]["gate"][path] = forged
                with self.assertRaisesRegex(ValueError, "receipt_binding_digest_mismatch"):
                    present_demo_policy_result(r)

    def test_recipe_cannot_claim_unearned_recovery(self):
        r = receipt()
        r["projection"]["recipe_id"] = "glpi-api-ticket-note"
        r["projection"]["gate"]["recipe_id"] = "glpi-api-ticket-note"
        with self.assertRaisesRegex(ValueError, "recipe_target_scope_invalid"):
            present_demo_policy_result(r)
        r = receipt("SIMULATED_NO_RECOVERY")
        r["projection"]["recipe_id"] = "glpi-api-ticket-note"
        r["projection"]["gate"]["recipe_id"] = "glpi-api-ticket-note"
        # The existing catalog scopes GLPI ticket notes to ACME-GLPI-*.
        r["projection"]["target_ci"] = "ACME-GLPI-01"
        r["projection"]["gate"]["target_ci"] = "ACME-GLPI-01"
        for snapshot in ("before", "after"):
            r["projection"][snapshot]["target_ci"] = "ACME-GLPI-01"
        r["projection"]["rollback"]["projected_state"]["target_ci"] = "ACME-GLPI-01"
        self.assertEqual(present_demo_policy_result(r)["policy"]["decision"], "SIMULATE")

    def test_recipe_catalog_and_target_scope_fail_closed(self):
        for recipe_id, version, target, error in (
            ("nonexistent-remediation", "1.0.0", "ACME-LNX-01", "recipe_not_allowlisted"),
            ("ansible-service-restart", "99.0.0", "ACME-LNX-01", "recipe_not_allowlisted"),
            ("ansible-service-restart", "1.0.0", "ACME-GLPI-01", "recipe_target_scope_invalid"),
            ("ansible-service-restart", "1.0.0", "<script>", "target_identity_invalid"),
        ):
            with self.subTest(recipe_id=recipe_id, version=version, target=target):
                r = receipt()
                r["projection"]["recipe_id"] = recipe_id
                r["projection"]["gate"]["recipe_id"] = recipe_id
                r["projection"]["gate"]["recipe_version"] = version
                r["projection"]["target_ci"] = target
                r["projection"]["gate"]["target_ci"] = target
                for snapshot in ("before", "after"):
                    r["projection"][snapshot]["target_ci"] = target
                with self.assertRaisesRegex(ValueError, error):
                    present_demo_policy_result(r)

    def test_receipt_builder_shape_and_ref_validation(self):
        for change, error in (
            (lambda r: r["projection"].update(schema_version=2), "projection_schema_invalid"),
            (lambda r: r.update(scenario_id="bad/../path"), "scenario_identity_invalid"),
            (lambda r: r.update(evidence_ids=["bad/../ref"]), "evidence_refs_invalid"),
            (lambda r: r.update(evidence_ids=["EVD-2", "EVD-1"]), "evidence_refs_invalid"),
        ):
            with self.subTest(error=error):
                r = receipt()
                change(r)
                with self.assertRaisesRegex(ValueError, error):
                    present_demo_policy_result(r)

    def test_forged_idempotency_matching_gate_still_rejected(self):
        r = receipt()
        r["projection"]["idempotency_key"] = "f" * 64
        r["projection"]["gate"]["idempotency_key"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "idempotency_digest_mismatch"):
            present_demo_policy_result(r)

    def test_projection_reason_cannot_claim_runtime_success(self):
        for status in ("SIMULATED_SUCCESS", "SIMULATED_FAILURE", "SIMULATED_NO_RECOVERY"):
            with self.subTest(status=status):
                r = receipt(status)
                if status == "SIMULATED_NO_RECOVERY":
                    r["projection"]["recipe_id"] = "glpi-api-ticket-note"
                    r["projection"]["gate"]["recipe_id"] = "glpi-api-ticket-note"
                r["projection"]["reason"] = "RUNTIME_APPROVED"
                with self.assertRaisesRegex(ValueError, "projection_reason_inconsistent"):
                    present_demo_policy_result(r)

    def test_gate_reason_cannot_claim_real_authorization(self):
        r = receipt()
        r["projection"]["gate"]["reason"] = "HUMAN_APPROVAL_VERIFIED"
        with self.assertRaisesRegex(ValueError, "projection_reason_inconsistent"):
            present_demo_policy_result(r)

    def test_blocked_reason_must_match_known_local_gate(self):
        for gate_reason, projection_reason in (
            ("RUNTIME_APPROVED", "RUNTIME_APPROVED"),
            ("APPROVAL_EXPIRED", "HUMAN_DECISION_NOT_APPROVED"),
        ):
            with self.subTest(gate_reason=gate_reason):
                r = receipt("BLOCKED", "BLOCKED")
                r["projection"]["gate"]["reason"] = gate_reason
                r["projection"]["reason"] = projection_reason
                with self.assertRaisesRegex(ValueError, "projection_reason_inconsistent"):
                    present_demo_policy_result(r)

    def test_does_not_mutate_input(self):
        r = receipt(); before = copy.deepcopy(r)
        present_demo_policy_result(r)
        self.assertEqual(r, before)


if __name__ == "__main__":
    unittest.main()
