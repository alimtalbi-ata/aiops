"""Offline deterministic negative tests for synthetic signal envelope v1."""
import copy
import unittest
from scripts.aiops2_signal_envelope_guard_20261115 import normalize, deduplicate, SCHEMA

NOW = "2026-11-15T20:00:00Z"
BASE = dict(schema=SCHEMA, mode="DEMO", tenant="acme-demo", source="prometheus",
            source_instance="synthetic-1", event_id="evt-1",
            observed_at="2026-11-15T19:59:00Z", kind="metric", state="FIRING",
            metric=dict(name="synthetic_latency", value=4.0, unit="seconds", window_seconds=60))

class GuardTests(unittest.TestCase):
    def test_valid_synthetic(self):
        e = normalize(BASE, now=NOW)
        self.assertEqual((e["freshness"], e["state"]), ("FRESH", "FIRING"))
        self.assertEqual(len(deduplicate([e, e])), 1)

    def test_stale_unknown(self):
        e = dict(BASE, observed_at="2026-11-15T19:00:00Z")
        self.assertEqual(normalize(e, now=NOW)["state"], "UNKNOWN")

    def test_future_unknown(self):
        e = dict(BASE, observed_at="2026-11-15T20:01:00Z")
        self.assertEqual(normalize(e, now=NOW)["freshness"], "UNKNOWN")

    def test_live_refused(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, mode="LIVE"), now=NOW)

    def test_metric_missing_unit(self):
        e = copy.deepcopy(BASE)
        del e["metric"]["unit"]
        with self.assertRaises(ValueError):
            normalize(e, now=NOW)

    def test_nonfinite_refused(self):
        e = copy.deepcopy(BASE)
        e["metric"]["value"] = float("nan")
        with self.assertRaises(ValueError):
            normalize(e, now=NOW)

    def test_extra_fields_refused(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, query="arbitrary"), now=NOW)

    def test_duplicate_conflict(self):
        a = normalize(BASE, now=NOW)
        b = normalize(dict(BASE, state="RESOLVED"), now=NOW)
        with self.assertRaises(ValueError):
            deduplicate([a, b])

    def test_source_identity_isolated(self):
        a = normalize(BASE, now=NOW)
        b = normalize(dict(BASE, source="grafana"), now=NOW)
        self.assertEqual(len(deduplicate([a, b])), 2)

    def test_tenant_identity_isolated(self):
        a = normalize(BASE, now=NOW)
        b = normalize(dict(BASE, tenant="other-demo"), now=NOW)
        self.assertEqual(len(deduplicate([a, b])), 2)

    def test_naive_timestamp_refused(self):
        with self.assertRaises(ValueError):
            normalize(dict(BASE, observed_at="2026-11-15T19:59:00"), now=NOW)

if __name__ == "__main__":
    unittest.main()
