"""Offline tests of run-bound ACME synthetic remediation receipts."""
import unittest
from datetime import datetime, timezone

from app.shared.remediation_lab import validate_proposal
from app.shared.acme_remediation_receipt import build_run_remediation_receipt

NOW = datetime(2026, 10, 27, 19, 24, tzinfo=timezone.utc)


def fixture():
    run = {"run_id": "RUN-ACME-1", "scenario_id": "SCN-ACME-1", "mode": "DEMO", "synthetic": True}
    proposal = {
        "proposal_id": "P-1", "recipe_id": "ansible-service-restart",
        "recipe_version": "1.0.0", "target_ci": "ACME-LNX-01",
        "parameters": {"service": "erp", "credential_ref": "vault://acme/erp"},
        "mode": "DEMO", "requested_by": "analyst-1",
    }
    _, digest = validate_proposal(proposal)
    decision = {
        "state": "APPROVED", "proposal_digest": digest, "actor_id": "operator-2",
        "actor_role": "approver", "authenticated": True,
        "expires_at": "2026-10-27T20:00:00Z", "requested_by": "analyst-1",
    }
    checks = {"ci_fresh": True, "owner_fenced": True, "service_exists": True, "maintenance_window": True}
    before = {"target_ci": "ACME-LNX-01", "health": "DEGRADED", "service_available": False}
    return run, proposal, decision, checks, before


class RunBoundReceiptTests(unittest.TestCase):
    def receipt(self, *args, **kwargs):
        return build_run_remediation_receipt(*args, now=NOW, **kwargs)

    def test_receipt_is_explicitly_unverified_and_non_effectful(self):
        r = self.receipt(*fixture(), ["EVD-1"])
        self.assertEqual(r["run_id"], "RUN-ACME-1")
        self.assertEqual(r["classification"], "SYNTHETIC_UNVERIFIED")
        self.assertFalse(r["core_run_verified"])
        self.assertFalse(r["evidence_verified"])
        self.assertFalse(r["persisted"])
        self.assertFalse(r["effect_applied"])
        self.assertEqual(r["projection"]["status"], "SIMULATED_SUCCESS")
        self.assertNotIn("vault://", str(r))

    def test_failure_receipt_keeps_rollback_projected(self):
        r = self.receipt(*fixture(), ["EVD-1"], outcome="FAILURE")
        self.assertEqual(r["projection"]["status"], "SIMULATED_FAILURE")
        self.assertEqual(r["projection"]["rollback"]["status"], "PROJECTED_ONLY")

    def test_evidence_order_does_not_change_digest(self):
        a = self.receipt(*fixture(), ["EVD-2", "EVD-1"])
        b = self.receipt(*fixture(), ["EVD-1", "EVD-2"])
        self.assertEqual(a, b)

    def test_evidence_binding_changes_digest(self):
        a = self.receipt(*fixture(), ["EVD-1"])
        b = self.receipt(*fixture(), ["EVD-2"])
        self.assertNotEqual(a["receipt_digest"], b["receipt_digest"])

    def test_invalid_or_duplicate_evidence_rejected(self):
        for refs in ([], ["EVD-1", "EVD-1"], ["../secret"], ["EVD-1"] * 33):
            with self.subTest(refs=refs):
                with self.assertRaisesRegex(ValueError, "evidence_refs_invalid"):
                    self.receipt(*fixture(), refs)

    def test_run_mode_mismatch_rejected(self):
        args = list(fixture())
        args[0]["mode"] = "REPLAY"
        with self.assertRaisesRegex(ValueError, "run_proposal_mode_mismatch"):
            self.receipt(*args, ["EVD-1"])

    def test_live_run_rejected(self):
        args = list(fixture())
        args[0]["mode"] = "LIVE"
        args[1]["mode"] = "LIVE"
        with self.assertRaisesRegex(ValueError, "run_not_synthetic"):
            self.receipt(*args, ["EVD-1"])

    def test_non_synthetic_run_rejected(self):
        args = list(fixture())
        args[0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "run_not_synthetic"):
            self.receipt(*args, ["EVD-1"])

    def test_run_identifier_validated(self):
        args = list(fixture())
        args[0]["run_id"] = "not-a-run"
        with self.assertRaisesRegex(ValueError, "run_id_invalid"):
            self.receipt(*args, ["EVD-1"])

    def test_rejected_approval_remains_blocked(self):
        args = list(fixture())
        args[2]["state"] = "REJECTED"
        r = self.receipt(*args, ["EVD-1"])
        self.assertEqual(r["projection"]["status"], "BLOCKED")
        self.assertEqual(r["projection"]["after"], args[4])


if __name__ == "__main__":
    unittest.main()
