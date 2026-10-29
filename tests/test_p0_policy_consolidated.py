import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from policy.main import Decision, evaluate, autonomy_store


BASE = {
    "mode": "DEMO",
    "command": "OBSERVE",
    "severity": "P2",
    "confidence": 0.95,
    "evidence_count": 2,
    "critic_validated": True,
    "redundancy_ok": True,
    "evidence_fresh": True,
}


class PolicyP0Tests(unittest.TestCase):

    def decide(self, autonomy="NORMAL", emergency="false", **changes):
        payload = {**BASE, **changes}
        with (
            patch.object(
                autonomy_store,
                "status",
                return_value={"mode": autonomy, "healthy": True},
            ),
            patch.dict(
                os.environ,
                {"AIOPS_POLICY_EMERGENCY_STOP": emergency},
            ),
        ):
            return evaluate(Decision(**payload))

    def test_strict_booleans(self):
        for field in (
            "critic_validated",
            "redundancy_ok",
            "evidence_fresh",
        ):
            for invalid in ("true", "false", 1, 0):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ValidationError):
                        Decision(**{**BASE, field: invalid})

    def test_qualified_simulation(self):
        result = self.decide()
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "SIMULATE")

    def test_synthetic_evidence_guards(self):
        cases = [
            ({"critic_validated": False}, "BLOCKED"),
            ({"redundancy_ok": False}, "BLOCKED"),
            ({"evidence_fresh": False}, "BLOCKED"),
            ({"confidence": 0.89}, "BLOCKED"),
            ({"evidence_count": 0}, "UNKNOWN"),
        ]
        for changes, expected in cases:
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.decide(**changes)["state"],
                    expected,
                )

    def test_confidence_threshold(self):
        self.assertEqual(
            self.decide(confidence=0.90)["state"],
            "PASS",
        )

    def test_stop_auto(self):
        result = self.decide(
            autonomy="STOP_AUTO",
            command="EXECUTE",
        )
        self.assertEqual(
            result["reason"],
            "AUTONOMOUS_REMEDIATION_SUSPENDED",
        )

    def test_freeze(self):
        result = self.decide(
            autonomy="FREEZE",
            command="EXECUTE",
        )
        self.assertEqual(
            result["reason"],
            "FREEZE_RESTRICTS_OPERATION_CLASS",
        )

    def test_emergency_stop(self):
        result = self.decide(
            emergency="true",
            command="EXECUTE",
        )
        self.assertIn(
            "EMERGENCY_STOP_ACTIVE",
            result["reason"],
        )

    def test_unknown_freeze_status(self):
        result = self.decide(command="EXECUTE")
        self.assertIn(
            "FREEZE_STATUS_UNKNOWN",
            result["reason"],
        )

    def test_live_p1_escalation(self):
        result = self.decide(mode="LIVE", severity="P1")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_live_effect_never_qualified(self):
        result = self.decide(
            mode="LIVE",
            command="EXECUTE",
            freeze_active=False,
            preconditions_verified=True,
            fencing_verified=True,
            human_approved=True,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "LIVE_EFFECTS_NOT_QUALIFIED",
            result["reason"],
        )

    def test_autonomy_unavailable(self):
        with patch.object(
            autonomy_store,
            "status",
            return_value={"mode": "NORMAL", "healthy": False},
        ):
            result = evaluate(Decision(**BASE))
        self.assertEqual(
            result["reason"],
            "AUTONOMY_STATE_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
