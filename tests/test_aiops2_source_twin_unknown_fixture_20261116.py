"""Offline contract assertions: synthetic sources never prove CMDB or LIVE impact."""
import json
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "aiops2_source_twin_unknown_20261116.json"


def identity(tenant, signal):
    return (tenant, signal["provider"], signal["instance"], signal["event_id"])


def edge_state(relation):
    # Synthetic claims are never qualified GLPI evidence.
    if relation.get("authority") != "GLPI_VERIFIED" or relation.get("attested") is not True:
        return "UNKNOWN"
    return "SOURCED"


class SourceTwinUnknownFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_version_and_simulation_fence(self):
        self.assertEqual(self.data["schema"], "aiops2.source-twin-boundary-fixture.v1")
        self.assertEqual(self.data["mode"], "SIMULATION")

    def test_provider_identity_is_not_collapsed_by_event_id(self):
        signals = self.data["signals"]
        self.assertEqual({s["provider"] for s in signals}, {"Checkmk", "Prometheus", "Grafana"})
        self.assertEqual(len({identity(self.data["tenant"], s) for s in signals}), 3)

    def test_tenant_participates_in_identity(self):
        signal = self.data["signals"][0]
        self.assertNotEqual(identity("acme-demo", signal), identity("other-demo", signal))

    def test_edges_are_unknown_without_verified_glpi(self):
        self.assertEqual([edge_state(r) for r in self.data["relations"]], self.data["expected_edges"])
        self.assertEqual(self.data["expected_payments_impact"], "UNKNOWN")

    def test_complete_shape_does_not_imply_proven_causality(self):
        edges = {(r["from"], r["to"]) for r in self.data["relations"]}
        self.assertEqual(edges, {("san-1", "storage-1"), ("storage-1", "payments-1")})
        self.assertFalse(all(edge_state(r) == "SOURCED" for r in self.data["relations"]))

    def test_false_attestation_and_unverified_authority_fail_closed(self):
        self.assertEqual(edge_state({"authority": "GLPI_VERIFIED", "attested": "true"}), "UNKNOWN")
        self.assertEqual(edge_state({"authority": "CMDB_SYNTHETIC", "attested": True}), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
