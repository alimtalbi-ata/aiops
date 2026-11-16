"""Offline contract regression: correlation cannot invent a CMDB/Twin path.

Synthetic fixtures only. No network, credentials, LIVE effects or runtime imports.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact

NOW = "2026-11-16T06:00:00Z"
DIGEST = "a" * 64


def event(**changes):
    value = dict(tenant_id="demo", source="checkmk", source_event_id="san-alarm",
                 ci_id="san-demo", service_id="payments-demo", severity="P1",
                 evidence_sha256=DIGEST, observed_at=NOW, known_at=NOW)
    value.update(changes)
    return value


def edge(origin, destination, **changes):
    value = dict(tenant_id="demo", from_id=origin, to_id=destination,
                 source_id="cmdb-fixture-only", evidence_sha256=DIGEST,
                 observed_at=NOW)
    value.update(changes)
    return value


def incident():
    result = correlate_events([event()], as_of=NOW)
    assert len(result["incidents"]) == 1
    return result["incidents"][0]


class CorrelationTwinChainBoundary(unittest.TestCase):
    def test_missing_storage_to_payments_is_unknown(self):
        result = resolve_impact(incident(), [edge("san-demo", "storage-demo")], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertEqual(result["paths"], [])

    def test_complete_fixture_path_never_attests_live(self):
        result = resolve_impact(incident(), [
            edge("san-demo", "storage-demo"),
            edge("storage-demo", "payments-demo"),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "SOURCED_SYNTHETIC_PATH")
        self.assertEqual(result["paths"][0]["nodes"],
                         ["san-demo", "storage-demo", "payments-demo"])
        self.assertIs(result["runtime_attested"], False)
        self.assertIs(result["live_remediation_authorized"], False)

    def test_cross_tenant_edge_cannot_complete_chain(self):
        result = resolve_impact(incident(), [
            edge("san-demo", "storage-demo"),
            edge("storage-demo", "payments-demo", tenant_id="other"),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertTrue(any(x["reason"] == "tenant mismatch" for x in result["rejected_edges"]))

    def test_future_proof_cannot_complete_chain(self):
        result = resolve_impact(incident(), [
            edge("san-demo", "storage-demo"),
            edge("storage-demo", "payments-demo", observed_at="2026-11-16T06:00:01Z"),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")

    def test_conflicting_relation_digests_quarantined(self):
        result = resolve_impact(incident(), [
            edge("san-demo", "storage-demo"),
            edge("storage-demo", "payments-demo"),
            edge("storage-demo", "payments-demo", evidence_sha256="b" * 64),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertTrue(any("conflicting" in x["reason"] for x in result["rejected_edges"]))

    def test_correlation_does_not_claim_impact_or_live(self):
        result = correlate_events([
            event(), event(source="prometheus", source_event_id="storage-alert",
                           ci_id="storage-demo"),
            event(source="grafana", source_event_id="payments-alert",
                  ci_id="payments-demo"),
        ], as_of=NOW)
        self.assertEqual(result["incidents"][0]["event_count"], 3)
        self.assertEqual(result["incidents"][0]["impact_state"], "UNKNOWN")
        self.assertIs(result["live_remediation_authorized"], False)


if __name__ == "__main__":
    unittest.main()
