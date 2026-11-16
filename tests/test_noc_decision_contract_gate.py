"""Unit tests for the isolated NOC decision contract gate."""
import unittest
from scripts.noc_decision_contract_gate import validate


def sample():
    return {
        "mode": "SIMULATION",
        "correlation": {"alerts": ["SAN_LATENCY", "DB_TIMEOUT"]},
        "impact_path": ["SAN", "DB-PAY", "Payments"],
        "evidence": [{"source": "synthetic-fixture", "status": "UNKNOWN"}],
        "analyst": {"hypothesis": "SAN saturation", "confidence": "LOW"},
        "critic": {"hypothesis": "Alternative DB contention", "confidence": "UNKNOWN"},
        "policy": {"decision": "DENY_LIVE", "hitl": "REQUIRED"},
        "next_action": {"type": "VERIFY_EVIDENCE", "effect": "NONE"},
    }


class NocDecisionGateTests(unittest.TestCase):
    def test_synthetic_fail_closed_passes(self):
        self.assertEqual(validate(sample()), [])

    def test_live_is_rejected(self):
        s = sample(); s["mode"] = "LIVE"
        self.assertIn("MODE_NOT_ISOLATED", validate(s))

    def test_missing_provenance_rejected(self):
        s = sample(); s["evidence"] = [{"status": "ATTESTED"}]
        self.assertIn("EVIDENCE_PROVENANCE_UNKNOWN", validate(s))

    def test_policy_approval_rejected(self):
        s = sample(); s["policy"]["decision"] = "ALLOW_LIVE"
        self.assertIn("POLICY_FAIL_CLOSED_REQUIRED", validate(s))

    def test_effectful_action_rejected(self):
        s = sample(); s["next_action"]["effect"] = "WRITE"
        self.assertIn("ACTION_NOT_READ_ONLY", validate(s))

    def test_missing_critic_rejected(self):
        s = sample(); del s["critic"]
        self.assertIn("CRITIC_HYPOTHESIS_MISSING", validate(s))

    def test_invalid_path_rejected(self):
        s = sample(); s["impact_path"] = ["SAN", "ERP"]
        self.assertIn("IMPACT_PATH_UNSUPPORTED", validate(s))

    def test_not_a_snapshot_rejected(self):
        self.assertIn("SNAPSHOT_NOT_OBJECT", validate([]))


if __name__ == "__main__":
    unittest.main()
