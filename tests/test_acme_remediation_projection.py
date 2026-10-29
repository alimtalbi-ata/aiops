"""Pure synthetic ACME remediation projection tests; no Docker or external I/O."""
import unittest
from datetime import datetime, timezone

from app.shared.remediation_lab import validate_proposal
from app.shared.acme_remediation_projection import project_remediation

NOW = datetime(2026, 10, 27, 19, 24, tzinfo=timezone.utc)


def fixture(mode="DEMO"):
    proposal = {
        "proposal_id": "P-ACME-1",
        "recipe_id": "ansible-service-restart",
        "recipe_version": "1.0.0",
        "target_ci": "ACME-LNX-01",
        "parameters": {"service": "erp", "credential_ref": "vault://acme/erp"},
        "mode": mode,
        "requested_by": "analyst-1",
    }
    _, digest = validate_proposal(proposal)
    decision = {
        "state": "APPROVED",
        "proposal_digest": digest,
        "actor_id": "operator-2",
        "actor_role": "approver",
        "authenticated": True,
        "expires_at": "2026-10-27T20:00:00Z",
        "requested_by": "analyst-1",
    }
    preconditions = {
        "ci_fresh": True,
        "owner_fenced": True,
        "service_exists": True,
        "maintenance_window": True,
    }
    before = {"target_ci": "ACME-LNX-01", "health": "DEGRADED", "service_available": False}
    return proposal, decision, preconditions, before


class AcmeProjectionTests(unittest.TestCase):
    def test_success_projects_state_without_effect(self):
        p, d, c, b = fixture()
        result = project_remediation(p, d, c, b, now=NOW)
        self.assertEqual(result["status"], "SIMULATED_SUCCESS")
        self.assertEqual(result["before"]["health"], "DEGRADED")
        self.assertEqual(result["after"]["health"], "HEALTHY")
        self.assertTrue(result["after"]["service_available"])
        self.assertEqual(result["postchecks"], "NOT_RUN")
        self.assertFalse(result["effect_applied"])
        self.assertEqual(result["provenance"], "WHAT_IF_FIXTURE_NOT_OBSERVED")
        self.assertEqual(b["health"], "DEGRADED")
        self.assertNotIn("vault://", str(result))

    def test_failure_projects_rollback_without_effect(self):
        p, d, c, b = fixture()
        result = project_remediation(p, d, c, b, outcome="FAILURE", now=NOW)
        self.assertEqual(result["status"], "SIMULATED_FAILURE")
        self.assertEqual(result["after"], b)
        self.assertEqual(result["rollback"]["projected_state"], b)
        self.assertFalse(result["rollback"]["effect_applied"])

    def test_live_always_blocked(self):
        p, d, c, b = fixture(mode="LIVE")
        result = project_remediation(p, d, c, b, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "LIVE_NOT_QUALIFIED")
        self.assertEqual(result["after"], b)

    def test_rejected_approval_does_not_change_state(self):
        p, d, c, b = fixture()
        d["state"] = "REJECTED"
        result = project_remediation(p, d, c, b, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["after"], b)

    def test_missing_precondition_does_not_change_state(self):
        p, d, c, b = fixture()
        c["owner_fenced"] = False
        result = project_remediation(p, d, c, b, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["after"], b)

    def test_wrong_target_rejected(self):
        p, d, c, b = fixture()
        b["target_ci"] = "ACME-LNX-OTHER"
        with self.assertRaisesRegex(ValueError, "before_target_mismatch"):
            project_remediation(p, d, c, b, now=NOW)

    def test_invalid_outcome_rejected(self):
        p, d, c, b = fixture()
        with self.assertRaisesRegex(ValueError, "unsupported_outcome"):
            project_remediation(p, d, c, b, outcome="LIVE_EXECUTE", now=NOW)

    def test_idempotent_projection(self):
        p, d, c, b = fixture()
        a = project_remediation(p, d, c, b, now=NOW)
        again = project_remediation(p, d, c, b, now=NOW)
        self.assertEqual(a, again)


if __name__ == "__main__":
    unittest.main()
