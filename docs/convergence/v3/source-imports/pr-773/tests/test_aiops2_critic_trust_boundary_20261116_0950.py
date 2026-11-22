"""Offline synthetic trust-boundary regressions. No LLM, GLPI or Temporal."""
import hashlib
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from aiops2_analyst_critic import analyze_and_critique
from aiops2_event_correlation import InvalidEvent

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def fixture():
    incident = dict(tenant_id="demo-acme", incident_id="SAN-001", service_id="Payments",
        runtime_attested=False, live_remediation_authorized=False,
        events=[dict(tenant_id="demo-acme", service_id="Payments", ci_id="SAN", evidence_sha256=sha("event"))])
    impact = dict(tenant_id="demo-acme", incident_id="SAN-001", service_id="Payments",
        runtime_attested=False, live_remediation_authorized=False,
        resource_budget_exhausted=False, impact_state="SOURCED_SYNTHETIC_PATH",
        paths=[dict(nodes=["SAN", "Payments"], evidence_sha256=[sha("edge")])])
    return incident, impact

class CriticTrustBoundary(unittest.TestCase):
    def test_synthetic_supported_is_not_live_authority(self):
        incident, impact = fixture()
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "SUPPORTED_SYNTHETIC_HYPOTHESIS")
        self.assertFalse(result["critic"]["root_cause_confirmed"])
        self.assertFalse(result["critic"]["runtime_attested"])
        self.assertEqual(result["analyst"]["kind"], "HYPOTHESIS_NOT_ROOT_CAUSE")
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")
        self.assertFalse(result["live_remediation_authorized"])

    def test_substituted_hashes_are_not_authoritative_receipts(self):
        incident, impact = fixture()
        incident["events"][0]["evidence_sha256"] = sha("untrusted-event")
        impact["paths"][0]["evidence_sha256"] = [sha("untrusted-edge")]
        result = analyze_and_critique(incident, impact)
        # Characterization of a known gap, not a successful provenance check.
        self.assertTrue(result["critic"]["citations_valid"])
        self.assertFalse(result["critic"]["runtime_attested"])
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")

    def test_unknown_dependency_requires_evidence(self):
        incident, impact = fixture()
        impact.update(impact_state="UNKNOWN", paths=[])
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "NEEDS_MORE_EVIDENCE")
        self.assertIn("SOURCED_DEPENDENCY_PATH", result["analyst"]["missing_evidence"])

    def test_cross_tenant_event_is_rejected(self):
        incident, impact = fixture()
        incident["events"][0]["tenant_id"] = "other-tenant"
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_forged_runtime_attestation_is_rejected(self):
        incident, impact = fixture()
        impact["runtime_attested"] = True
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_budget_exhaustion_cannot_claim_path(self):
        incident, impact = fixture()
        impact["resource_budget_exhausted"] = True
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)
