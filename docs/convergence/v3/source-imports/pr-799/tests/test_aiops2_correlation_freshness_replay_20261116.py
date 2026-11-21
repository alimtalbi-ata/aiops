"""Offline replay regression for canonical synthetic event correlation; no network/LIVE."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts" / "aiops2_event_correlation.py"
spec = importlib.util.spec_from_file_location("aiops2_event_correlation", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = "2026-11-16T15:00:00Z"

def event(source="checkmk", event_id="evt-1", tenant="tenant-fixture",
          observed="2026-11-16T14:59:00Z", known="2026-11-16T14:59:01Z",
          severity="P2"):
    return {"tenant_id": tenant, "source": source, "source_event_id": event_id,
            "ci_id": "ci-fixture", "service_id": "payments-fixture",
            "severity": severity, "evidence_sha256": "a" * 64,
            "observed_at": observed, "known_at": known}

class ReplayBoundaryTests(unittest.TestCase):
    def correlate(self, rows):
        return module.correlate_events(rows, as_of=NOW, max_age_seconds=900)

    def test_identical_replay_deduplicates(self):
        a = event()
        result = self.correlate([a, dict(a)])
        self.assertEqual(result["incidents"][0]["event_count"], 1)
        self.assertEqual(result["rejected"], [])

    def test_conflict_quarantines_both_orders(self):
        a, b = event(), event(severity="P1")
        for rows in ([a, b], [b, a]):
            with self.subTest(rows=rows):
                result = self.correlate(rows)
                self.assertEqual(result["incidents"], [])
                self.assertEqual(len(result["rejected"]), 2)

    def test_third_replay_cannot_resurrect_conflict(self):
        a, b = event(), event(severity="P1")
        result = self.correlate([a, b, a])
        self.assertEqual(result["incidents"], [])
        self.assertEqual(len(result["rejected"]), 3)

    def test_source_identity_isolated(self):
        rows = [event(source=s) for s in ("checkmk", "prometheus", "grafana")]
        result = self.correlate(rows)
        self.assertEqual(result["incidents"][0]["event_count"], 3)
        self.assertEqual(result["incidents"][0]["impact_state"], "UNKNOWN")
        self.assertFalse(result["live_remediation_authorized"])

    def test_tenant_identity_isolated(self):
        result = self.correlate([event(tenant="tenant-a"), event(tenant="tenant-b")])
        self.assertEqual(len(result["incidents"]), 2)
        self.assertNotEqual(result["incidents"][0]["incident_id"], result["incidents"][1]["incident_id"])

    def test_freshness_boundary_inclusive(self):
        result = self.correlate([event(observed="2026-11-16T14:45:00Z")])
        self.assertEqual(len(result["incidents"]), 1)

    def test_stale_and_future_rejected(self):
        rows = [event(event_id="old", observed="2026-11-16T14:44:59Z"),
                event(event_id="future", observed="2026-11-16T15:00:01Z",
                      known="2026-11-16T15:00:01Z")]
        result = self.correlate(rows)
        self.assertEqual(result["incidents"], [])
        self.assertEqual(len(result["rejected"]), 2)

    def test_future_knowledge_rejected(self):
        result = self.correlate([event(known="2026-11-16T15:00:01Z")])
        self.assertEqual(result["incidents"], [])
        self.assertEqual(len(result["rejected"]), 1)

if __name__ == "__main__":
    unittest.main()
