"""Isolated Analyst/Critic boundary characterization; no LLM, network or LIVE effects.

Run from repository root:
  PYTHONPATH=scripts python -m unittest discover -s tests -p 'test_aiops2_intelligence_freshness_boundary_20261116.py' -v

These tests deliberately distinguish an upstream freshness gate from the
downstream deterministic Analyst/Critic, which DOES NOT attest freshness.
"""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from aiops2_analyst_critic import analyze_and_critique
from aiops2_event_correlation import InvalidEvent, correlate_events


DIGEST_EVENT = "a" * 64
DIGEST_EDGE = "b" * 64


def raw_event(observed_at, tenant="tenant-synthetic"):
    return {
        "tenant_id": tenant, "source": "prometheus",
        "source_event_id": "san-degraded-1", "ci_id": "san-01",
        "service_id": "payments", "severity": "P1",
        "evidence_sha256": DIGEST_EVENT,
        "observed_at": observed_at, "known_at": observed_at,
    }


def sourced_impact(incident):
    return {
        "tenant_id": incident["tenant_id"],
        "incident_id": incident["incident_id"],
        "service_id": incident["service_id"],
        "runtime_attested": False,
        "live_remediation_authorized": False,
        "resource_budget_exhausted": False,
        "impact_state": "SOURCED_SYNTHETIC_PATH",
        "paths": [{"nodes": ["san-01", "payments"],
                   "evidence_sha256": [DIGEST_EDGE]}],
    }


class IntelligenceFreshnessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
        self.as_of = self.now.isoformat()
        self.fresh = (self.now - timedelta(seconds=10)).isoformat()
        self.stale = (self.now - timedelta(hours=2)).isoformat()

    def test_fresh_correlated_synthetic_path_still_denies_live(self):
        receipt = correlate_events([raw_event(self.fresh)], as_of=self.as_of)
        self.assertEqual(len(receipt["incidents"]), 1)
        incident = receipt["incidents"][0]
        result = analyze_and_critique(incident, sourced_impact(incident))
        self.assertEqual(result["critic"]["disposition"], "SUPPORTED_SYNTHETIC_HYPOTHESIS")
        self.assertFalse(result["critic"]["root_cause_confirmed"])
        self.assertFalse(result["critic"]["runtime_attested"])
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")
        self.assertFalse(result["live_remediation_authorized"])

    def test_stale_event_rejected_at_correlation_boundary(self):
        receipt = correlate_events([raw_event(self.stale)], as_of=self.as_of)
        self.assertEqual(receipt["incidents"], [])
        self.assertEqual(len(receipt["rejected"]), 1)
        self.assertIn("freshness", receipt["rejected"][0]["reason"])

    def test_cross_tenant_impact_is_rejected(self):
        incident = correlate_events([raw_event(self.fresh)], as_of=self.as_of)["incidents"][0]
        impact = sourced_impact(incident)
        impact["tenant_id"] = "other-tenant"
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_direct_analyst_call_does_not_attest_freshness(self):
        # Characterization, NOT a security guarantee: direct callers must
        # supply an authoritative freshness/ACL gate before this module.
        incident = correlate_events([raw_event(self.fresh)], as_of=self.as_of)["incidents"][0]
        incident = copy.deepcopy(incident)
        incident["events"][0]["observed_at"] = self.stale
        result = analyze_and_critique(incident, sourced_impact(incident))
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertFalse(result["critic"]["root_cause_confirmed"])


if __name__ == "__main__":
    unittest.main()
