"""Offline regression for aiops2.source-proof-gate.v1."""
import unittest
from scripts.aiops2_source_proof_gate_20261116 import normalize, deduplicate, correlate

NOW = "2026-11-16T10:00:00Z"
BASE = dict(mode="SIMULATION", tenant="demo-acme", source="checkmk", instance="lab-1",
            event_id="synthetic-001", ci_id="demo-san", observed_at=NOW)


class SourceProofGateTests(unittest.TestCase):
    def test_synthetic_only(self):
        self.assertEqual(normalize(BASE, NOW)["status"], "SOURCED_SYNTHETIC")
        self.assertEqual(normalize({**BASE, "mode": "LIVE"}, NOW)["status"], "UNKNOWN")

    def test_source_identity_isolated(self):
        ids = [normalize({**BASE, "source": s}, NOW)["identity"] for s in ("checkmk", "prometheus", "grafana")]
        self.assertEqual(len(set(ids)), 3)

    def test_tenant_identity_isolated(self):
        self.assertNotEqual(normalize(BASE, NOW)["identity"], normalize({**BASE, "tenant": "other"}, NOW)["identity"])

    def test_freshness_boundary(self):
        old = {**BASE, "observed_at": "2026-11-16T09:55:00Z"}
        self.assertEqual(normalize(old, NOW)["status"], "SOURCED_SYNTHETIC")
        self.assertEqual(normalize(old, NOW, 299)["status"], "UNKNOWN")

    def test_future_and_timezone_rejected(self):
        for value in ("2026-11-16T10:00:01Z", "2026-11-16T10:00:00+00:00", "garbage"):
            self.assertEqual(normalize({**BASE, "observed_at": value}, NOW)["status"], "UNKNOWN")

    def test_invalid_thresholds(self):
        for threshold in (True, None, -1, 1.5):
            self.assertEqual(normalize(BASE, NOW, threshold)["status"], "UNKNOWN")

    def test_exact_duplicate(self):
        r = normalize(BASE, NOW)
        self.assertEqual(deduplicate([r, r]), [r])

    def test_conflicting_duplicate(self):
        r = normalize(BASE, NOW)
        self.assertEqual(deduplicate([r, {**r, "ci_id": "demo-storage"}])[0]["status"], "UNKNOWN")

    def test_correlation_no_causality(self):
        a = normalize(BASE, NOW)
        b = normalize({**BASE, "source": "grafana"}, NOW)
        self.assertEqual(correlate([a, b]), {"status": "SYNTHETIC_CANDIDATE", "incident_id": None, "causality": "UNKNOWN"})

    def test_cross_tenant_unknown(self):
        self.assertEqual(correlate([normalize(BASE, NOW), normalize({**BASE, "tenant": "other"}, NOW)])["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
