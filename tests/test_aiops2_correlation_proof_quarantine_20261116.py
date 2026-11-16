"""Offline regression: contradictory event/CMDB proof must not establish Payments impact.

Synthetic fixtures only. No adapters, sockets, live effects or real metrics.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact

NOW = "2026-11-16T12:00:00Z"
D1 = "a" * 64
D2 = "b" * 64


def event(source="checkmk", event_id="evt-1", digest=D1):
    return dict(tenant_id="demo-acme", source=source, source_event_id=event_id,
                ci_id="san-demo", service_id="payments-demo", severity="P1",
                evidence_sha256=digest, observed_at=NOW, known_at=NOW)


def edge(origin, target, digest=D1, observed=NOW, tenant="demo-acme", source="fixture-cmdb"):
    return dict(tenant_id=tenant, from_id=origin, to_id=target,
                source_id=source, evidence_sha256=digest, observed_at=observed)


class QuarantineProofTests(unittest.TestCase):
    def test_conflicting_duplicate_quarantined_in_both_orders(self):
        a, b = event(), event(digest=D2)
        for receipts in ((a, b), (b, a)):
            with self.subTest(order=receipts[0]["evidence_sha256"]):
                result = correlate_events(list(receipts), as_of=NOW)
                self.assertEqual(result["incidents"], [])
                self.assertEqual(len(result["rejected"]), 2)
                self.assertFalse(result["live_remediation_authorized"])

    def test_cross_source_same_event_id_remains_distinct(self):
        result = correlate_events([event("checkmk"), event("prometheus"), event("grafana")], as_of=NOW)
        self.assertEqual(len(result["incidents"]), 1)
        self.assertEqual(result["incidents"][0]["event_count"], 3)
        self.assertEqual(result["incidents"][0]["impact_state"], "UNKNOWN")

    def test_conflicting_storage_payments_relation_quarantines_path(self):
        incident = correlate_events([event()], as_of=NOW)["incidents"][0]
        edges = [edge("san-demo", "storage-demo"),
                 edge("storage-demo", "payments-demo", D1),
                 edge("storage-demo", "payments-demo", D2, source="other-fixture")]
        result = resolve_impact(incident, edges, as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertEqual(result["paths"], [])
        self.assertTrue(result["rejected_edges"])
        self.assertFalse(result["runtime_attested"])

    def test_stale_storage_payments_proof_cannot_complete_path(self):
        incident = correlate_events([event()], as_of=NOW)["incidents"][0]
        edges = [edge("san-demo", "storage-demo"),
                 edge("storage-demo", "payments-demo", observed="2026-11-14T00:00:00Z")]
        result = resolve_impact(incident, edges, as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertEqual(result["paths"], [])
        self.assertEqual(result["rejected_edges"][0]["reason"], "stale or future edge")

    def test_only_synthetic_complete_chain_is_sourced(self):
        incident = correlate_events([event()], as_of=NOW)["incidents"][0]
        result = resolve_impact(incident,
            [edge("san-demo", "storage-demo"), edge("storage-demo", "payments-demo")],
            as_of=NOW)
        self.assertEqual(result["impact_state"], "SOURCED_SYNTHETIC_PATH")
        self.assertEqual(result["paths"][0]["nodes"],
                         ["san-demo", "storage-demo", "payments-demo"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertFalse(result["runtime_attested"])


if __name__ == "__main__":
    unittest.main()
