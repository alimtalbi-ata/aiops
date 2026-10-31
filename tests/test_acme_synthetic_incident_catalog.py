"""Isolated, offline ACME synthetic catalog/replay contracts (no live systems)."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import generate_acme_incidents as gen


class AcmeSyntheticIncidentCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = gen.load_graph()
        cls.catalog, cls.catalog_sha = gen.load_catalog()

    def test_exact_graph_and_registered_scenario_ids(self):
        self.assertEqual(self.graph["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual((len(self.graph["nodes"]), len(self.graph["edges"])), (18, 17))
        self.assertEqual(len(self.graph["scenario_ids"]), 4)
        self.assertIn("SCN-GOLDEN-PAYMENT-P1", self.graph["scenario_ids"])

    def test_ten_categories_four_graph_bound_six_blocked(self):
        items = self.catalog["scenarios"]
        self.assertEqual(len(items), 10)
        self.assertEqual(sum(s["status"] == "SUPPORTED_BY_SEED" for s in items), 4)
        self.assertEqual(sum(s["status"] == "BLOCKED_MISSING_CMDB_CI" for s in items), 6)
        self.assertEqual({s["severity_synthetic"] for s in items}, {"P1", "P2", "P3", "P4"})
        self.assertIsNone(next(s for s in items if s["key"] == "DB_LATENCY")["scenario_id"])
        self.assertEqual(self.catalog["tenant_scope"], "UNKNOWN")
        self.assertIsNone(self.catalog["observed_at"])
        self.assertIsNone(self.catalog["known_at"])
        self.assertEqual(self.catalog["freshness"], "UNKNOWN")

    def test_golden_seven_pinned_checkpoints_not_runtime_events(self):
        result = gen.replay(graph=self.graph)
        self.assertEqual(result["scenario_id"], "SCN-GOLDEN-PAYMENT-P1")
        self.assertEqual(result["event_count"], 7)
        self.assertEqual([e["at_seconds"] for e in result["events"]], [0, 15, 30, 45, 60, 90, 110])
        self.assertEqual([e["action"] for e in result["events"]], [
            "INCIDENT_OPEN", "SET_STATE", "OBSERVE", "CHANGE_LOOKUP",
            "POLICY_CHECK", "VERIFY", "RECONCILE"])
        self.assertEqual(result["events"][2]["payload"]["value"], 184)
        self.assertEqual(result["events"][5]["payload"], {"latency_ms": 92, "status": "OK"})
        self.assertEqual(result["events"][6]["payload"]["state"], "DEGRADED")

    def test_san_to_payments_uses_real_edge_ids_reverse_direction(self):
        impact = gen.replay(graph=self.graph)["impact_estimate"]
        self.assertEqual(impact["path_edge_ids"], ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(impact["path_node_ids"], [
            "ACME-SAN-FABRIC-A", "ACME-STO-PURE01", "ACME-VM-PAY01",
            "ACME-APP-ORACLEPAY", "ACME-SVC-PAYMENTS"])
        self.assertEqual(self.graph["edges"]["ACME-E01"]["source_id"], "ACME-BIZ-PAYMENTS")
        self.assertEqual(self.graph["edges"]["ACME-E09"]["target_id"], "ACME-SAN-FABRIC-B")
        self.assertFalse(impact["redundancy_evaluated"])
        self.assertEqual(impact["observed_service_impact"], "UNKNOWN")

    def test_blast_radius_is_candidate_not_observed_impact(self):
        impact = gen.replay()["impact_estimate"]
        self.assertEqual(impact["candidate_service_ids"], ["ACME-SVC-ERP", "ACME-SVC-PAYMENTS"])
        self.assertGreater(impact["candidate_ci_count"], 5)
        self.assertFalse(impact["causality_verified"])
        self.assertEqual(impact["estimated_impact_level"], "HIGH")

    def test_itil_priority_and_roles_are_only_synthetic_proposal(self):
        result = gen.replay()
        self.assertEqual(result["itil"]["priority_candidate"], "P1")
        self.assertEqual(result["itil"]["priority_confirmed"], "UNKNOWN")
        self.assertEqual(result["itil"]["roles_planned"], ["N1", "N2", "N3", "INCIDENT_COMMANDER"])
        self.assertFalse(result["itil"]["roles_authenticated"])
        self.assertEqual(result["itil"]["priority_rule"], "ACME_OFFLINE_MATRIX_V1")

    def test_all_events_have_source_simulated_timestamps_and_unknown_tenant(self):
        result = gen.replay()
        self.assertEqual(result["tenant_scope"], "UNKNOWN")
        for event in result["events"]:
            self.assertEqual(event["source"], gen.SOURCE)
            self.assertEqual(event["provenance"], "SYNTHETIC_FIXTURE")
            self.assertEqual(event["freshness"], "SYNTHETIC_CLOCK_ONLY")
            self.assertEqual(event["tenant_scope"], "UNKNOWN")
            self.assertIsNone(event["tenant_id"])
            self.assertIsNone(event["evidence_id"])
            self.assertTrue(event["source_event_id"].startswith("SYN-EVT-"))
            self.assertLessEqual(event["observed_at"], event["known_at"])
            self.assertEqual(gen.synthetic_freshness(event), "SYNTHETIC_CLOCK_ONLY")

    def test_replay_determinism_seed_and_content_hash(self):
        a, b = gen.replay(seed=20261018), gen.replay(seed=20261018)
        self.assertEqual(gen._canonical(a), gen._canonical(b))
        self.assertEqual(a["dataset_sha256"], b["dataset_sha256"])
        self.assertNotEqual(a["dataset_sha256"], gen.replay(seed=20261019)["dataset_sha256"])
        self.assertEqual(a["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual(a["catalog_sha256"], self.catalog_sha)

    def test_stochastic_mode_is_seeded_and_golden_never_jittered(self):
        a = gen.replay("CAPACITY_PRESSURE", seed=42, stochastic=True)
        b = gen.replay("CAPACITY_PRESSURE", seed=42, stochastic=True)
        c = gen.replay("CAPACITY_PRESSURE", seed=43, stochastic=True)
        self.assertEqual(a, b)
        self.assertNotEqual(a["dataset_sha256"], c["dataset_sha256"])
        self.assertEqual(a["scenario_id"], "SCN-STORAGE-CAPACITY-P2")
        with self.assertRaises(ValueError):
            gen.replay(stochastic=True)
        with self.assertRaises(ValueError):
            gen.replay(false_positive=True)
        cmd = [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
               "--scenario", "CAPACITY_PRESSURE", "--stochastic"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("requires explicit --seed", proc.stderr)

    def test_network_and_capacity_edges_are_from_pinned_graph(self):
        network = gen.replay("NETWORK_FAILURE")
        capacity = gen.replay("CAPACITY_PRESSURE")
        self.assertEqual(network["impact_estimate"]["path_edge_ids"], ["ACME-E12", "ACME-E03"])
        self.assertEqual(capacity["impact_estimate"]["path_edge_ids"], ["ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(network["itil"]["priority_candidate"], "P2")
        self.assertTrue(all(e["synthetic"] for e in network["events"] + capacity["events"]))

    def test_unsupported_categories_fail_closed_without_fabricated_ci(self):
        for item in self.catalog["scenarios"]:
            if item["status"] == "BLOCKED_MISSING_CMDB_CI":
                with self.subTest(category=item["key"]), self.assertRaisesRegex(ValueError, "BLOCKED_MISSING_CMDB_CI"):
                    gen.replay(item["key"])
                self.assertIsNone(item["source_ci_id"])
                self.assertIsNone(item["service_id"])

    def test_maintenance_window_suppresses_priority(self):
        result = gen.replay("APPLICATION_DEGRADATION")
        self.assertEqual(result["itil"]["priority_candidate"], "UNKNOWN")
        self.assertTrue(any(e["maintenance_window_active"] for e in result["events"]))
        self.assertFalse(result["publishable_to_core_or_glpi"])

    def test_false_positive_never_escalates(self):
        result = gen.replay("NETWORK_FAILURE", false_positive=True)
        self.assertEqual(result["itil"]["priority_candidate"], "UNKNOWN")
        self.assertTrue(all(e["payload"]["classification"] == "NORMAL_SYNTHETIC"
                            for e in result["events"] if e["action"] == "OBSERVE"))

    def test_multici_correlation_and_exact_event_dedup(self):
        events = gen.replay()["events"]
        grouped = gen.correlate_offline(events + [copy.deepcopy(events[0])])
        self.assertEqual(grouped["event_count"], 7)
        self.assertEqual(grouped["ci_ids"], ["ACME-SAN-FABRIC-A", "ACME-SVC-PAYMENTS"])
        self.assertFalse(grouped["publishable"])
        self.assertEqual(grouped["tenant_scope"], "UNKNOWN")

    def test_tenant_and_event_identity_conflicts_are_rejected(self):
        events = gen.replay()["events"]
        foreign = copy.deepcopy(events)
        foreign[0]["tenant_id"] = "TEST-ONLY-OTHER-TENANT"
        with self.assertRaisesRegex(ValueError, "tenant/identity"):
            gen.correlate_offline(foreign)
        conflicting = copy.deepcopy(events)
        conflicting[0]["payload"] = {"forged": True}
        with self.assertRaisesRegex(ValueError, "conflicting source event"):
            gen.correlate_offline(events + conflicting[:1])
        with self.assertRaisesRegex(ValueError, "unrelated scenarios"):
            gen.correlate_offline(events + gen.replay("NETWORK_FAILURE")["events"])

    def test_offline_correlation_rejects_forged_ci_source_or_evidence(self):
        events = gen.replay()["events"]
        mutations = (
            ("ci_id", "ACME-NOT-IN-PINNED-GRAPH"),
            ("source", "UNTRUSTED_FAKE_MONITOR"),
            ("id_authority", "CORE_VERIFIED"),
            ("source_event_id", "SYN-EVT-FORGED"),
            ("evidence_id", "EVIDENCE-NEVER-READ-FROM-API"),
            ("observed_impact", "CONFIRMED"),
            ("synthetic", False),
            ("freshness", "LIVE"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                tampered = copy.deepcopy(events)
                tampered[0][field] = value
                with self.assertRaisesRegex(ValueError, "untrusted synthetic event"):
                    gen.correlate_offline(tampered)
        self.assertEqual(gen.correlate_offline(events)["event_count"], 7)

    def test_offline_correlation_rejects_stale_non_utc_or_reordered_time(self):
        events = gen.replay()["events"]
        mutations = (
            ("known_at", "2026-10-31T10:00:00Z"),
            ("known_at", "2026-10-31T09:42:01+00:00"),
            ("known_at", "2026-10-31T09:41:59Z"),
            ("event_time", "2026-10-31T09:42:01Z"),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                tampered = copy.deepcopy(events)
                tampered[0][field] = value
                with self.assertRaisesRegex(ValueError, "stale or invalid synthetic event chronology"):
                    gen.correlate_offline(tampered)

    def test_stale_and_invalid_time_never_become_real_freshness(self):
        event = copy.deepcopy(gen.replay()["events"][0])
        event["known_at"] = "2026-10-31T10:00:00Z"
        self.assertEqual(gen.synthetic_freshness(event), "STALE_SYNTHETIC")
        event["known_at"] = "invalid"
        self.assertEqual(gen.synthetic_freshness(event), "UNKNOWN")

    def test_glpi_core_run_evidence_resolution_reopen_are_not_faked(self):
        result = gen.replay()
        for key in ("tenant_id", "incident_id", "run_id", "ticket_id"):
            self.assertIsNone(result[key])
        self.assertEqual(result["evidence_ids"], [])
        self.assertEqual([x["stage"] for x in result["checkpoints"]], list(gen.CHECKPOINTS))
        self.assertTrue(all(x["status"] == "NOT_EXECUTED" and x["id"] is None
                            for x in result["checkpoints"]))
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])

    def test_tampered_graph_and_catalog_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seed.sql"
            p.write_bytes(gen.SEED_FILE.read_bytes().replace(b"ACME-E08", b"ACME-E99"))
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                gen.load_graph(p)
            c = Path(d) / "catalog.json"
            c.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                gen.load_catalog(c)

    def test_cli_artifact_is_reproducible_and_sha_matches(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "replay.json"
            cmd = [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
                   "--scenario", "REDUNDANT_SAN_PATH_LOSS", "--seed", "20261018",
                   "--output", str(out)]
            first = subprocess.run(cmd, capture_output=True, text=True, check=True)
            raw = out.read_bytes()
            second = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertEqual(raw, out.read_bytes())
            self.assertEqual(json.loads(first.stdout)["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(json.loads(raw)["event_count"], 7)


if __name__ == "__main__":
    unittest.main()
