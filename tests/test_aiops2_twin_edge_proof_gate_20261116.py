"""Synthetic, offline-only edge gate regression tests."""
import copy
import unittest
from scripts.aiops2_twin_edge_proof_gate_20261116 import CONTRACT, evaluate
NOW = "2026-11-16T12:00:00Z"

def fixture():
    def edge(a, aid, b, bid):
        return {"from_type": a, "from_id": aid, "to_type": b, "to_id": bid,
                "tenant": "synthetic-acme", "authority": "CMDB", "attested": True,
                "evidence_ref": "fixture-only", "observed_at": "2026-11-16T11:59:00Z"}
    return {"contract": CONTRACT, "mode": "SIMULATION", "tenant": "synthetic-acme",
            "edges": [edge("SAN", "san-1", "STORAGE", "storage-1"),
                      edge("STORAGE", "storage-1", "PAYMENTS", "payments-1")]}

class TwinEdgeProofTests(unittest.TestCase):
    def test_complete_synthetic_only(self):
        result = evaluate(fixture(), NOW)
        self.assertEqual(result["status"], "SOURCED_SYNTHETIC_PATH")
        self.assertEqual(result["path"], ["san-1", "storage-1", "payments-1"])
        self.assertIs(result["live_authorized"], False)

    def test_missing_edge_unknown(self):
        p = fixture(); p["edges"].pop()
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_live_unknown(self):
        p = fixture(); p["mode"] = "LIVE"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_tenant_mismatch_unknown(self):
        p = fixture(); p["edges"][1]["tenant"] = "other"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_stale_unknown(self):
        p = fixture(); p["edges"][1]["observed_at"] = "2026-11-16T11:54:59Z"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_future_unknown(self):
        p = fixture(); p["edges"][1]["observed_at"] = "2026-11-16T12:00:01Z"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_duplicate_unknown(self):
        p = fixture(); p["edges"].append(copy.deepcopy(p["edges"][1]))
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_broken_chain_unknown(self):
        p = fixture(); p["edges"][1]["from_id"] = "storage-2"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_provenance_unknown(self):
        for key, value in [("attested", "true"), ("evidence_ref", ""), ("authority", "Twin")]:
            with self.subTest(key=key):
                p = fixture(); p["edges"][0][key] = value
                self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_non_utc_unknown(self):
        p = fixture(); p["edges"][0]["observed_at"] = "2026-11-16T11:59:00+01:00"
        self.assertEqual(evaluate(p, NOW)["status"], "UNKNOWN")

    def test_exact_freshness_boundary(self):
        p = fixture(); p["edges"][0]["observed_at"] = "2026-11-16T11:55:00Z"
        self.assertEqual(evaluate(p, NOW)["status"], "SOURCED_SYNTHETIC_PATH")

if __name__ == "__main__":
    unittest.main()
