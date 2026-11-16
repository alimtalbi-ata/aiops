"""Offline-only directional and time-boundary tests for synthetic CMDB/Twin proof.

Fixture evidence is not authenticated GLPI evidence; LIVE remains NO-GO.
"""
import unittest

from scripts.aiops2_twin_proof_boundary_20261116 import project

NODES = [
    {"id": "san-x", "kind": "SAN", "tenant": "demo"},
    {"id": "disk-x", "kind": "STORAGE", "tenant": "demo"},
    {"id": "payments-x", "kind": "SERVICE", "tenant": "demo"},
]
NOW = "2026-11-16T00:05:00Z"
PROOF = {
    "source": "san-x", "target": "disk-x", "tenant": "demo",
    "authority": "CMDB", "evidence_id": "fixture-only",
    "observed_at": "2026-11-16T00:00:00Z", "attested": True,
}


class TwinDirectionTimeBoundaryTests(unittest.TestCase):
    def statuses(self, edges, **kwargs):
        result = project(NODES, edges, tenant="demo", now=NOW, **kwargs)
        self.assertEqual(result["schema"], "aiops2.twin-proof-boundary.v1")
        self.assertEqual(result["mode"], "DEMO")
        self.assertIs(result["live_attested"], False)
        return [edge["status"] for edge in result["edges"]]

    def test_reverse_direction_does_not_establish_san_storage(self):
        self.assertEqual(
            self.statuses([dict(PROOF, source="disk-x", target="san-x")]),
            ["UNKNOWN", "UNKNOWN"],
        )

    def test_unrelated_edge_does_not_prove_payments(self):
        self.assertEqual(
            self.statuses([PROOF, dict(PROOF, source="san-x", target="payments-x")]),
            ["SOURCED_SYNTHETIC", "UNKNOWN"],
        )

    def test_complete_fixture_path_is_synthetic_only(self):
        result = self.statuses([
            PROOF, dict(PROOF, source="disk-x", target="payments-x",
                        evidence_id="fixture-payments"),
        ])
        self.assertEqual(result, ["SOURCED_SYNTHETIC", "SOURCED_SYNTHETIC"])

    def test_no_nodes_or_edges_stays_unknown(self):
        result = project([], [], tenant="demo", now=NOW)
        self.assertEqual([e["status"] for e in result["edges"]],
                         ["UNKNOWN", "UNKNOWN"])
        self.assertIs(result["live_attested"], False)

    def test_non_utc_now_fails_closed(self):
        with self.assertRaises(ValueError):
            project(NODES, [PROOF], tenant="demo", now="2026-11-16T00:05:00+01:00")

    def test_duplicate_node_id_across_kinds_fails_closed(self):
        with self.assertRaises(ValueError):
            project([NODES[0], dict(NODES[1], id="san-x"), NODES[2]],
                    [PROOF], tenant="demo", now=NOW)

    def test_malformed_unrelated_edge_fails_closed(self):
        with self.assertRaises(ValueError):
            self.statuses([PROOF, {"source": "disk-x", "target": "san-x"}])


if __name__ == "__main__":
    unittest.main()
