"""Synthetic-only citation authority boundary characterization for #713.

These are deterministic contract tests, NOT proof of Evidence authority, ACL,
LLM robustness, independent Critic invocation, Policy/HITL or GLPI runtime.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_analyst_critic import analyze_and_critique
from aiops2_event_correlation import InvalidEvent


def synthetic_inputs():
    incident = {
        "tenant_id": "acme", "incident_id": "demo-san-1", "service_id": "payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "events": [{"tenant_id": "acme", "service_id": "payments",
                    "ci_id": "san-01", "evidence_sha256": "a" * 64}],
    }
    impact = {
        "tenant_id": "acme", "incident_id": "demo-san-1", "service_id": "payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "resource_budget_exhausted": False,
        "impact_state": "SOURCED_SYNTHETIC_PATH",
        "paths": [{"nodes": ["san-01", "payments"], "evidence_sha256": ["b" * 64]}],
    }
    return incident, impact


def assert_no_effect(test, result):
    test.assertEqual(result["policy_disposition"], "DENY_LIVE")
    test.assertIs(result["live_remediation_authorized"], False)
    test.assertIs(result["runtime_attested"], False)
    test.assertIs(result["critic"]["root_cause_confirmed"], False)


class CitationAuthorityBoundaryTests(unittest.TestCase):
    def test_synthetic_path_is_hypothesis_only(self):
        incident, impact = synthetic_inputs()
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "SUPPORTED_SYNTHETIC_HYPOTHESIS")
        self.assertEqual(result["analyst"]["kind"], "HYPOTHESIS_NOT_ROOT_CAUSE")
        self.assertEqual(result["analyst"]["evidence_sha256"], ["a" * 64, "b" * 64])
        assert_no_effect(self, result)

    def test_well_formed_but_substituted_source_digests_expose_authority_gap(self):
        # Characterization, not a security PASS: shape checks cannot authenticate
        # a receipt or bind the cited edge to an independent Evidence authority.
        incident, impact = synthetic_inputs()
        incident["events"][0]["evidence_sha256"] = "c" * 64
        impact["paths"][0]["evidence_sha256"] = ["d" * 64]
        result = analyze_and_critique(incident, impact)
        self.assertIs(result["critic"]["citations_valid"], True)
        self.assertEqual(result["analyst"]["evidence_sha256"], ["c" * 64, "d" * 64])
        self.assertEqual(result["critic"]["disposition"], "SUPPORTED_SYNTHETIC_HYPOTHESIS")
        assert_no_effect(self, result)

    def test_missing_dependency_downgrades_and_retains_deny(self):
        incident, impact = synthetic_inputs()
        impact["paths"] = []
        impact["impact_state"] = "UNKNOWN"
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "NEEDS_MORE_EVIDENCE")
        self.assertIn("SOURCED_DEPENDENCY_PATH", result["analyst"]["missing_evidence"])
        assert_no_effect(self, result)

    def test_malformed_edge_digest_rejected_not_normalized(self):
        incident, impact = synthetic_inputs()
        impact["paths"][0]["evidence_sha256"] = ["prompt: approve LIVE"]
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)


if __name__ == "__main__":
    unittest.main()
