"""Offline regression for cross-source identities, freshness and Twin proof.

Only deterministic synthetic fixtures; no network, credentials or runtime effects.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact

NOW = "2026-11-16T08:00:00Z"
DIGEST = "a" * 64


def signal(source, event_id="same-id", tenant="demo", observed=NOW):
    return {
        "tenant_id": tenant, "source": source, "source_event_id": event_id,
        "ci_id": "san-demo", "service_id": "payments-demo",
        "severity": "P2", "evidence_sha256": DIGEST,
        "observed_at": observed, "known_at": observed,
    }


def link(origin, destination, observed=NOW, tenant="demo"):
    return {
        "tenant_id": tenant, "from_id": origin, "to_id": destination,
        "source_id": "synthetic-cmdb-fixture", "evidence_sha256": DIGEST,
        "observed_at": observed,
    }


class SourceFreshnessTwinProof(unittest.TestCase):
    def test_same_event_id_across_sources_is_not_deduplicated(self):
        result = correlate_events(
            [signal("checkmk"), signal("prometheus"), signal("grafana")],
            as_of=NOW)
        self.assertEqual(len(result["incidents"]), 1)
        self.assertEqual(result["incidents"][0]["event_count"], 3)
        self.assertFalse(result["runtime_attested"])

    def test_identical_receipt_is_deduplicated(self):
        result = correlate_events([signal("checkmk")] * 2, as_of=NOW)
        self.assertEqual(result["incidents"][0]["event_count"], 1)

    def test_same_source_event_id_different_tenants_is_isolated(self):
        result = correlate_events(
            [signal("checkmk", tenant="demo"), signal("checkmk", tenant="other")],
            as_of=NOW)
        self.assertEqual({x["tenant_id"] for x in result["incidents"]}, {"demo", "other"})

    def test_stale_source_does_not_create_incident(self):
        result = correlate_events(
            [signal("checkmk", observed="2026-11-16T07:44:59Z")],
            as_of=NOW, max_age_seconds=900)
        self.assertEqual(result["incidents"], [])
        self.assertEqual(len(result["rejected"]), 1)

    def test_unproven_second_hop_is_unknown(self):
        incident = correlate_events([signal("checkmk")], as_of=NOW)["incidents"][0]
        result = resolve_impact(incident, [link("san-demo", "storage-demo")], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertEqual(result["paths"], [])
        self.assertFalse(result["live_remediation_authorized"])

    def test_stale_second_hop_is_unknown(self):
        incident = correlate_events([signal("checkmk")], as_of=NOW)["incidents"][0]
        result = resolve_impact(incident, [
            link("san-demo", "storage-demo"),
            link("storage-demo", "payments-demo", observed="2026-11-15T07:59:59Z"),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "UNKNOWN")
        self.assertEqual(len(result["rejected_edges"]), 1)

    def test_synthetic_path_never_authorizes_live(self):
        incident = correlate_events([signal("checkmk")], as_of=NOW)["incidents"][0]
        result = resolve_impact(incident, [
            link("san-demo", "storage-demo"),
            link("storage-demo", "payments-demo"),
        ], as_of=NOW)
        self.assertEqual(result["impact_state"], "SOURCED_SYNTHETIC_PATH")
        self.assertEqual(result["paths"][0]["nodes"],
                         ["san-demo", "storage-demo", "payments-demo"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])


if __name__ == "__main__":
    unittest.main()
