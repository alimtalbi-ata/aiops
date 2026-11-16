"""Additional offline-only regression matrix for the synthetic Twin proof boundary.

No network, real CMDB queries, or LIVE claims.
"""
import unittest

from scripts.aiops2_twin_proof_boundary_20261116 import project

NOW = "2026-11-16T00:05:00Z"
NODES = [
    {"id": "san-fixture", "kind": "SAN", "tenant": "fixture"},
    {"id": "storage-fixture", "kind": "STORAGE", "tenant": "fixture"},
    {"id": "payments-fixture", "kind": "SERVICE", "tenant": "fixture"},
]
EDGE = {
    "source": "san-fixture", "target": "storage-fixture",
    "tenant": "fixture", "authority": "CMDB", "evidence_id": "fixture-proof",
    "observed_at": "2026-11-16T00:00:00Z", "attested": True,
}


class TwinAdditionalBoundaryTests(unittest.TestCase):
    def statuses(self, nodes=NODES, edges=None, **kwargs):
        result = project(nodes, [EDGE] if edges is None else edges,
                         tenant="fixture", now=NOW, **kwargs)
        self.assertEqual(result["mode"], "DEMO")
        self.assertIs(result["live_attested"], False)
        return [edge["status"] for edge in result["edges"]]

    def test_exact_freshness_limit_is_inclusive(self):
        self.assertEqual(self.statuses(max_age_seconds=300),
                         ["SOURCED_SYNTHETIC", "UNKNOWN"])

    def test_one_second_past_limit_is_unknown(self):
        self.assertEqual(self.statuses(max_age_seconds=299),
                         ["UNKNOWN", "UNKNOWN"])

    def test_declared_non_cmdb_authority_cannot_prove_edge(self):
        self.assertEqual(self.statuses(edges=[dict(EDGE, authority="Twin")]),
                         ["UNKNOWN", "UNKNOWN"])

    def test_non_boolean_attestation_is_not_evidence(self):
        self.assertEqual(self.statuses(edges=[dict(EDGE, attested=1)]),
                         ["UNKNOWN", "UNKNOWN"])

    def test_missing_san_node_does_not_infer_path(self):
        self.assertEqual(self.statuses(nodes=NODES[1:], edges=[]),
                         ["UNKNOWN", "UNKNOWN"])

    def test_duplicate_storage_node_is_rejected(self):
        duplicate = dict(NODES[1], id="storage-other")
        with self.assertRaises(ValueError):
            self.statuses(nodes=NODES + [duplicate])

    def test_dangling_relation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.statuses(edges=[dict(EDGE, target="unregistered")])

    def test_cross_tenant_node_is_rejected(self):
        with self.assertRaises(ValueError):
            self.statuses(nodes=[dict(NODES[0], tenant="foreign")] + NODES[1:])


if __name__ == "__main__":
    unittest.main()
