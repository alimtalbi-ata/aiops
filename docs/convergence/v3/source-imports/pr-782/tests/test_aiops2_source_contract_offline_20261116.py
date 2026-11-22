"""Isolated regression tests: synthetic source identity, freshness, dedup and UNKNOWN."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "aiops2_source_contract_offline_20261116.py"
spec = importlib.util.spec_from_file_location("aiops2_source_contract_offline", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = "2026-11-16T10:00:00Z"

def fixture(source="checkmk", tenant="demo-a", event="evt-1", ci="san-1"):
    return dict(contract_version=module.VERSION, mode="SIMULATION", tenant_id=tenant,
                source=source, source_instance="fixture-01", event_id=event,
                ci_id=ci, observed_at="2026-11-16T09:59:00Z")

class SourceContractBoundary(unittest.TestCase):
    def test_three_sources_have_distinct_identities(self):
        keys = {module.normalize(fixture(source=s), now=NOW)["identity_key"]
                for s in ("checkmk", "prometheus", "grafana")}
        self.assertEqual(len(keys), 3)

    def test_cross_tenant_isolation(self):
        a = module.normalize(fixture(tenant="a"), now=NOW)
        b = module.normalize(fixture(tenant="b"), now=NOW)
        self.assertEqual(len(module.correlate([a, b])), 2)

    def test_duplicate_is_idempotent(self):
        a = module.normalize(fixture(), now=NOW)
        self.assertEqual(len(module.correlate([a, a])[0]["signal_keys"]), 1)

    def test_contradictory_duplicate_rejected(self):
        a = module.normalize(fixture(), now=NOW)
        b = dict(a, ci_id="different")
        with self.assertRaisesRegex(ValueError, "CONTRADICTORY_DUPLICATE"):
            module.correlate([a, b])

    def test_forged_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "FORGED_IDENTITY"):
            module.normalize(dict(fixture(), identity_key="forged"), now=NOW)

    def test_stale_and_future_rejected(self):
        for timestamp in ("2026-11-16T09:54:59Z", "2026-11-16T10:00:01Z"):
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(ValueError, "UNTRUSTED_FRESHNESS"):
                module.normalize(dict(fixture(), observed_at=timestamp), now=NOW)

    def test_boundary_exact_age_allowed(self):
        e = module.normalize(dict(fixture(), observed_at="2026-11-16T09:55:00Z"), now=NOW)
        self.assertEqual(e["freshness"], "FRESH_SYNTHETIC")

    def test_invalid_age_rejected(self):
        for age in (True, -1, 1.5, float("nan"), None):
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, "INVALID_MAX_AGE"):
                module.normalize(fixture(), now=NOW, max_age_seconds=age)

    def test_live_and_non_utc_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_LIVE"):
            module.normalize(dict(fixture(), mode="LIVE"), now=NOW)
        with self.assertRaisesRegex(ValueError, "UTC_Z_REQUIRED"):
            module.normalize(dict(fixture(), observed_at="2026-11-16T09:59:00+01:00"), now=NOW)

    def test_correlation_never_infers_incident_or_cause(self):
        events = [module.normalize(fixture(source=s), now=NOW)
                  for s in ("checkmk", "prometheus", "grafana")]
        group, = module.correlate(events)
        self.assertEqual(group["causality"], "UNKNOWN")
        self.assertIsNone(group["incident_id"])
        self.assertEqual(len(group["signal_keys"]), 3)

if __name__ == "__main__":
    unittest.main()
