"""Critic v2.3 fail-closed model response regression tests.

Run: python -m unittest discover -s tests -p 'test_critic_v23.py' -v
No NIM/DGX calls or external effects.
"""
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SPEC = importlib.util.spec_from_file_location("aiops_critic_v23", ROOT / "app" / "intelligence" / "main.py")
AI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AI)


def candidate(**changes):
    data = {
        "validated": True,
        "issues": [],
        "claim_checks": [{
            "claim": "One SAN path failed",
            "supported": True,
            "supporting_evidence_ids": ["E1"],
            "contradicting_evidence_ids": [],
        }],
        "unsafe_actions": [],
        "diagnostic_confidence": 0.65,
        "final_recommendation": "OBSERVE",
    }
    data.update(changes)
    return data


class CriticV23Tests(unittest.TestCase):
    def test_issue_downgrades_to_human_approval_without_erasing_issue(self):
        issue = {"code": "SEVERITY_MISMATCH", "description": "P1 unproven", "evidence_ids": ["E1"]}
        actual = AI.downgrade_inconsistent_critic(candidate(issues=[issue]))
        parsed = AI.Critique.model_validate(actual)
        self.assertFalse(parsed.validated)
        self.assertEqual(parsed.final_recommendation, "HUMAN_APPROVAL")
        self.assertEqual(parsed.issues[0].code, "SEVERITY_MISMATCH")

    def test_unsupported_claim_downgrades(self):
        checks = [{"claim": "Service unavailable", "supported": False,
                   "supporting_evidence_ids": [], "contradicting_evidence_ids": ["E1"]}]
        parsed = AI.Critique.model_validate(
            AI.downgrade_inconsistent_critic(candidate(claim_checks=checks))
        )
        self.assertFalse(parsed.validated)
        self.assertFalse(parsed.claim_checks[0].supported)

    def test_unsafe_action_downgrades_and_preserves_escalate(self):
        parsed = AI.Critique.model_validate(
            AI.downgrade_inconsistent_critic(
                candidate(unsafe_actions=["Restart SAN switch"], final_recommendation="ESCALATE")
            )
        )
        self.assertFalse(parsed.validated)
        self.assertEqual(parsed.final_recommendation, "ESCALATE")
        self.assertEqual(parsed.unsafe_actions, ["Restart SAN switch"])

    def test_clean_critique_is_unchanged(self):
        src = candidate()
        self.assertIs(AI.downgrade_inconsistent_critic(src), src)
        self.assertTrue(AI.Critique.model_validate(src).validated)

    def test_negative_decision_is_never_promoted(self):
        src = candidate(validated=False, final_recommendation="HUMAN_APPROVAL")
        self.assertIs(AI.downgrade_inconsistent_critic(src), src)

    def test_missing_claim_checks_cannot_be_repaired(self):
        src = candidate(claim_checks=[])
        self.assertIs(AI.downgrade_inconsistent_critic(src), src)
        with self.assertRaises(ValidationError):
            AI.Critique.model_validate(src)

    def test_invalid_schema_remains_invalid(self):
        issue = {"code": "INVENTED_ISSUE", "description": "unknown"}
        src = AI.downgrade_inconsistent_critic(candidate(issues=[issue]))
        with self.assertRaises(ValidationError):
            AI.Critique.model_validate(src)

    def test_supported_claim_without_evidence_still_rejected(self):
        src = candidate(claim_checks=[{"claim":"x","supported":True,
                                       "supporting_evidence_ids":[]}])
        with self.assertRaises(ValidationError):
            AI.Critique.model_validate(AI.downgrade_inconsistent_critic(src))


if __name__ == "__main__":
    unittest.main()
