import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_signal_context import normalize_signals, build_signal_context, CLOCK
from portal.acme_twin_provenance import build_twin_evidence


class SignalContextTests(unittest.TestCase):
    def setUp(self):
        self.twin = build_twin_evidence((Path(__file__).resolve().parents[1] / "app/portal/acme-fixtures.json").read_bytes())
        self.event = dict(source="GRAFANA_FIXTURE", event_id="test", namespace="ACME-DEMO",
                          ci_id="SAN-FABRIC-A", state="firing", severity="critical", observed_at=CLOCK)

    def normalize(self, events):
        return normalize_signals(events, self.twin, as_of_utc=CLOCK)

    def test_demo(self):
        result = build_signal_context(self.twin)
        self.assertEqual((result["input_count"], result["unique_count"], result["duplicate_count"]), (3, 2, 1))
        self.assertEqual({s["priority"] for s in result["signals"]}, {"P1", "P2"})
        self.assertTrue(all(s["runtime_freshness"] == "UNKNOWN" for s in result["signals"]))
        self.assertFalse(result["runtime_attested"])

    def test_freshness_boundary(self):
        for observed, status in [(CLOCK, "FRESH"), ("2026-10-25T08:55:00Z", "FRESH"),
                                 ("2026-10-25T08:54:59Z", "STALE"), (None, "UNKNOWN")]:
            with self.subTest(observed=observed):
                self.assertEqual(self.normalize([{**self.event, "observed_at": observed}])["signals"][0]["scenario_freshness"]["status"], status)

    def test_conflicting_replay(self):
        with self.assertRaises(ValueError):
            self.normalize([self.event, {**self.event, "state": "resolved"}])

    def test_source_identity_and_determinism(self):
        other = {**self.event, "source": "PROMETHEUS_FIXTURE"}
        a = self.normalize([self.event, other])
        self.assertEqual(a, self.normalize([other, self.event]))
        self.assertEqual(a["unique_count"], 2)
        self.assertNotEqual(a["signals"][0]["signal_id"], a["signals"][1]["signal_id"])

    def test_fail_closed(self):
        for key, value in [("namespace", " acme "), ("source", "LIVE"), ("ci_id", "missing"),
                           ("severity", "P1"), ("observed_at", "2026-10-25T09:00:01Z"),
                           ("observed_at", "2026-10-25T09:00:00+00:00")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.normalize([{**self.event, key: value}])

    def test_alternative_not_impacted(self):
        result = self.normalize([{**self.event, "ci_id": "SAN-FABRIC-B"}])
        self.assertEqual(result["signals"][0]["correlation"], "OUTSIDE_IMPACT_PATH")

    def test_digest_changes_with_payload(self):
        a = self.normalize([self.event])["signals"][0]
        b = self.normalize([{**self.event, "severity": "warning"}])["signals"][0]
        self.assertEqual(a["signal_id"], b["signal_id"])
        self.assertNotEqual(a["provenance"]["event_sha256"], b["provenance"]["event_sha256"])

    def test_tenant_run_attempt_identity_is_explicitly_unbound(self):
        result = build_signal_context(self.twin)
        self.assertEqual(result["incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(result["impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertIsNone(result["tenant_id"])
        self.assertIsNone(result["attempt_id"])
        self.assertEqual(result["binding_status"], "UNBOUND")
        self.assertTrue(result["run_id"].startswith("SIM-ACME-"))

    def test_tampered_twin_identity_or_digest_rejected(self):
        import copy
        for key, value in [("tenant_id", "tenant-real"), ("attempt_id", "attempt-real"),
                           ("run_id", "RUN-123"), ("source_sha256", "0" * 64),
                           ("incident_id", "INC-OTHER"), ("observed_at", "2026-10-25T09:00:00Z"),
                           ("freshness", "FRESH"), ("binding_status", "BOUND")]:
            with self.subTest(key=key):
                twin = copy.deepcopy(self.twin)
                twin[key] = value
                with self.assertRaises(ValueError):
                    normalize_signals([self.event], twin, as_of_utc=CLOCK)

    def test_event_provenance_binds_source_and_timestamp(self):
        signal = self.normalize([self.event])["signals"][0]
        p = signal["provenance"]
        self.assertEqual(p["source"], "GRAFANA_FIXTURE")
        self.assertEqual(p["observed_at"], CLOCK)
        self.assertEqual(p["source_ref"], "inline://synthetic/GRAFANA_FIXTURE/test")
        self.assertEqual(len(p["event_sha256"]), 64)
        self.assertEqual(p["twin_source_sha256"], self.twin["source_sha256"])
