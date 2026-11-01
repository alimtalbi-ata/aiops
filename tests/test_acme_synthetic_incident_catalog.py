"""Isolated, offline ACME synthetic catalog/replay contracts (no live systems)."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import generate_acme_incidents as gen
from tools import acme_synthetic_ingest_contract as ingest


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

    def test_distinct_replay_modes_never_alias_source_dedupe_or_correlation_ids(self):
        """Same category and seed in different modes cannot share fixture identities."""
        modes = ((False, False), (True, False), (False, True), (True, True))
        manifests = [gen.replay("NETWORK_FAILURE", seed=99, stochastic=stochastic,
                                false_positive=false_positive)
                     for stochastic, false_positive in modes]
        for manifest, (_, false_positive) in zip(manifests, modes):
            events = manifest["events"]
            self.assertEqual(len({e["source_event_id"] for e in events}), len(events))
            self.assertEqual(len({e["correlation_key"] for e in events}), 1)
            self.assertEqual(gen.correlate_catalog_manifest_offline(
                manifest, false_positive=false_positive)["event_count"],
                manifest["event_count"])
        for i, left in enumerate(manifests):
            for j, right in enumerate(manifests[i + 1:], i + 1):
                with self.subTest(left_mode=modes[i], right_mode=modes[j]):
                    for field in ("source_event_id", "dedupe_key", "correlation_key"):
                        self.assertTrue(
                            {e[field] for e in left["events"]}.isdisjoint(
                                {e[field] for e in right["events"]}), field)
                    with self.assertRaisesRegex(ValueError, "unrelated scenarios"):
                        gen.correlate_offline(left["events"] + right["events"])
        self.assertEqual(gen.replay()["dataset_sha256"],
                         "ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f")

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

    def test_catalog_blob_pin_rejects_plausible_priority_edits_and_whitespace(self):
        raw = gen.CATALOG_FILE.read_bytes()
        self.assertEqual(gen._git_blob(raw), gen.CATALOG_GIT_BLOB)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "catalog.json"
            edited = copy.deepcopy(self.catalog)
            golden = next(s for s in edited["scenarios"]
                          if s["key"] == "REDUNDANT_SAN_PATH_LOSS")
            golden["urgency_synthetic"] = "HIGH"  # still valid schema, but unreviewed
            path.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "catalog Git blob mismatch"):
                gen.load_catalog(path)
            path.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "catalog Git blob mismatch"):
                gen.load_catalog(path)
        self.assertEqual(gen.replay()["dataset_sha256"],
                         "ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f")

    def test_tampered_graph_and_catalog_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seed.sql"
            p.write_bytes(gen.SEED_FILE.read_bytes().replace(b"ACME-E08", b"ACME-E99"))
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                gen.load_graph(p)
            c = Path(d) / "catalog.json"
            c.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "catalog Git blob mismatch"):
                gen.load_catalog(c)
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                json.loads(c.read_text(encoding="utf-8"), object_pairs_hook=gen._unique_object)

    def test_replay_rejects_injected_graph_even_with_valid_fixture_ids(self):
        forged = copy.deepcopy(self.graph)
        # A caller-provided graph with an invented direct dependency must not
        # bypass the pinned SQL Git blob simply because its CI IDs are valid.
        forged["consumers"]["ACME-SAN-FABRIC-A"].append(
            ("ACME-E08", "ACME-SVC-PAYMENTS"))
        with self.assertRaisesRegex(ValueError, "unpinned graph override"):
            gen.replay(graph=forged)
        self.assertEqual(
            gen.replay(graph=self.graph)["dataset_sha256"],
            "ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f")

    def test_replay_rejects_injected_catalog_priority(self):
        forged = copy.deepcopy(self.catalog)
        golden = next(s for s in forged["scenarios"]
                      if s["key"] == "REDUNDANT_SAN_PATH_LOSS")
        golden["urgency_synthetic"] = "LOW"
        with self.assertRaisesRegex(ValueError, "unpinned catalog override"):
            gen.replay(catalog=forged)
        self.assertEqual(
            gen.replay(catalog=self.catalog)["dataset_sha256"],
            "ce0aef74222699da695c2e894e622b0625c992ef654dda34a84cff26b5e64f3f")

    def test_strict_golden_manifest_correlates_only_complete_pinned_replay(self):
        manifest = gen.replay(seed=20261018)
        grouped = gen.correlate_golden_manifest_offline(manifest)
        self.assertEqual(grouped["event_count"], 7)
        self.assertEqual(grouped["ci_ids"], ["ACME-SAN-FABRIC-A", "ACME-SVC-PAYMENTS"])
        self.assertFalse(grouped["publishable"])
        self.assertEqual(grouped["tenant_scope"], "UNKNOWN")
        self.assertEqual(grouped["provenance"], "SYNTHETIC_FIXTURE")

    def test_strict_golden_manifest_rejects_forged_links_and_rehashed_payload(self):
        original = gen.replay()
        mutations = (
            ("tenant_id", lambda m: m.__setitem__("tenant_id", "UNVERIFIED-TENANT")),
            ("incident_id", lambda m: m.__setitem__("incident_id", "UNVERIFIED-INCIDENT")),
            ("run_id", lambda m: m.__setitem__("run_id", "UNVERIFIED-RUN")),
            ("ticket_id", lambda m: m.__setitem__("ticket_id", "UNVERIFIED-TICKET")),
            ("evidence_ids", lambda m: m.__setitem__("evidence_ids", ["UNVERIFIED-EVIDENCE"])),
            ("priority", lambda m: m["itil"].__setitem__("priority_confirmed", "P1")),
            ("observed_impact", lambda m: m["impact_estimate"].__setitem__("observed_service_impact", "HIGH")),
            ("checkpoint", lambda m: m["checkpoints"][0].__setitem__("status", "SUCCESS")),
            ("event_payload", lambda m: m["events"][2]["payload"].__setitem__("value", 0)),
            ("source_event_id", lambda m: m["events"][0].__setitem__("source_event_id", "SYN-EVT-AAAAAAAAAAAAAAAAAAAA")),
            ("maintenance", lambda m: m["events"][0].__setitem__("maintenance_window_active", True)),
            ("ci_id", lambda m: m["events"][0].__setitem__("ci_id", "ACME-SAN-FABRIC-B")),
            ("event_removed", lambda m: m["events"].pop()),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                forged = copy.deepcopy(original)
                mutate(forged)
                # Even a matching attacker-controlled checksum is not authority.
                unsigned = {k: v for k, v in forged.items() if k != "dataset_sha256"}
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(unsigned)).hexdigest()
                with self.assertRaisesRegex(ValueError, "golden replay manifest mismatch"):
                    gen.correlate_golden_manifest_offline(forged)
        for invalid in (None, {}, gen.replay("NETWORK_FAILURE"), gen.replay(seed=20261019), {"seed": True}):
            with self.subTest(invalid=str(type(invalid))):
                with self.assertRaisesRegex(ValueError, "untrusted golden replay manifest"):
                    gen.correlate_golden_manifest_offline(invalid)

    def test_strict_catalog_manifest_accepts_all_supported_non_golden_modes(self):
        for category in ("NETWORK_FAILURE", "CAPACITY_PRESSURE", "APPLICATION_DEGRADATION"):
            for stochastic in (False, True):
                with self.subTest(category=category, stochastic=stochastic):
                    manifest = gen.replay(category, seed=37, stochastic=stochastic)
                    grouped = gen.correlate_catalog_manifest_offline(manifest)
                    self.assertEqual(grouped["event_count"], manifest["event_count"])
                    self.assertFalse(grouped["publishable"])
                    self.assertEqual(grouped["tenant_scope"], "UNKNOWN")
                    self.assertEqual(grouped["provenance"], "SYNTHETIC_FIXTURE")
                    self.assertIsNone(manifest["incident_id"])
                    self.assertIsNone(manifest["run_id"])
                    self.assertIsNone(manifest["ticket_id"])
                    self.assertEqual(manifest["evidence_ids"], [])
                    self.assertTrue(all(c["status"] == "NOT_EXECUTED"
                                        for c in manifest["checkpoints"]))
        self.assertEqual(gen.correlate_catalog_manifest_offline(gen.replay())["event_count"], 7)

    def test_strict_catalog_manifest_rejects_rehashed_forged_links_and_observations(self):
        original = gen.replay("CAPACITY_PRESSURE", seed=37, stochastic=True)
        mutations = (
            ("tenant", lambda m: m.__setitem__("tenant_id", "UNVERIFIED")),
            ("incident", lambda m: m.__setitem__("incident_id", "UNVERIFIED")),
            ("run", lambda m: m.__setitem__("run_id", "UNVERIFIED")),
            ("ticket", lambda m: m.__setitem__("ticket_id", "UNVERIFIED")),
            ("evidence", lambda m: m.__setitem__("evidence_ids", ["UNVERIFIED"])),
            ("priority", lambda m: m["itil"].__setitem__("priority_confirmed", "P1")),
            ("impact", lambda m: m["impact_estimate"].__setitem__("observed_service_impact", "HIGH")),
            ("checkpoint", lambda m: m["checkpoints"][0].__setitem__("status", "SUCCESS")),
            ("metric", lambda m: m["events"][1]["payload"].__setitem__("value", 0)),
            ("source_event_id", lambda m: m["events"][0].__setitem__(
                "source_event_id", "SYN-EVT-AAAAAAAAAAAAAAAAAAAA")),
            ("maintenance", lambda m: m["events"][0].__setitem__("maintenance_window_active", True)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                forged = copy.deepcopy(original)
                mutate(forged)
                unsigned = {k: v for k, v in forged.items() if k != "dataset_sha256"}
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(unsigned)).hexdigest()
                with self.assertRaisesRegex(ValueError, "catalog replay manifest mismatch"):
                    gen.correlate_catalog_manifest_offline(forged)

    def test_strict_catalog_manifest_false_positive_requires_explicit_mode(self):
        false_alarm = gen.replay("NETWORK_FAILURE", seed=99, false_positive=True)
        self.assertEqual(false_alarm["itil"]["priority_candidate"], "UNKNOWN")
        with self.assertRaisesRegex(ValueError, "catalog replay manifest mismatch"):
            gen.correlate_catalog_manifest_offline(false_alarm)
        self.assertEqual(gen.correlate_catalog_manifest_offline(
            false_alarm, false_positive=True)["event_count"], false_alarm["event_count"])
        with self.assertRaisesRegex(ValueError, "golden replay cannot be a false positive"):
            gen.correlate_catalog_manifest_offline(gen.replay(), false_positive=True)
        for invalid in (None, {}, {"scenario_category": "CAPACITY_PRESSURE",
                                   "seed": True, "stochastic": False},
                        gen.replay("CAPACITY_PRESSURE", seed=37, stochastic=True)):
            with self.subTest(invalid=str(type(invalid))):
                with self.assertRaises(ValueError):
                    gen.correlate_catalog_manifest_offline(invalid, false_positive="yes")

    def test_strict_manifest_rejects_python_json_scalar_type_aliases(self):
        """Python True == 1 and 7 == 7.0 must not bypass a pinned replay."""
        cases = (
            ("synthetic_bool_as_int", lambda m: m.__setitem__("synthetic", 1)),
            ("no_live_effects_bool_as_int",
             lambda m: m.__setitem__("live_effects_authorized", 0)),
            ("count_int_as_float",
             lambda m: m.__setitem__("event_count", float(m["event_count"]))),
            ("roles_authenticated_bool_as_int",
             lambda m: m["itil"].__setitem__("roles_authenticated", 0)),
            ("event_maintenance_bool_as_int",
             lambda m: m["events"][0].__setitem__("maintenance_window_active", 0)),
        )
        for category in ("REDUNDANT_SAN_PATH_LOSS", "CAPACITY_PRESSURE"):
            baseline = gen.replay(category, seed=20261018)
            validator = (gen.correlate_golden_manifest_offline
                         if category == "REDUNDANT_SAN_PATH_LOSS"
                         else gen.correlate_catalog_manifest_offline)
            for label, mutate in cases:
                with self.subTest(category=category, mutation=label):
                    forged = copy.deepcopy(baseline)
                    mutate(forged)
                    # The old dict comparison accepted these different JSON
                    # representations with the unchanged dataset checksum.
                    self.assertEqual(forged, baseline)
                    self.assertNotEqual(gen._canonical(forged), gen._canonical(baseline))
                    with self.assertRaisesRegex(ValueError, "manifest mismatch"):
                        validator(forged)
                    with self.assertRaises(ValueError):
                        gen.storyboard_offline(forged)

    def test_every_supported_path_is_reverse_edge_sourced_without_runtime_attestation(self):
        """Check all catalog paths, not just Golden, against the pinned Twin edges."""
        for scenario in self.catalog["scenarios"]:
            if scenario["status"] != "SUPPORTED_BY_SEED":
                continue
            modes = (False,) if scenario["key"] == "REDUNDANT_SAN_PATH_LOSS" else (False, True)
            for stochastic in modes:
                with self.subTest(category=scenario["key"], stochastic=stochastic):
                    manifest = gen.replay(scenario["key"], seed=20261018,
                                          stochastic=stochastic)
                    impact = manifest["impact_estimate"]
                    nodes = impact["path_node_ids"]
                    edges = impact["path_edge_ids"]
                    self.assertEqual((nodes[0], nodes[-1]),
                                     (scenario["source_ci_id"], scenario["service_id"]))
                    self.assertEqual(len(edges), len(nodes) - 1)
                    for edge_id, dependency, consumer in zip(edges, nodes, nodes[1:]):
                        edge = self.graph["edges"][edge_id]
                        self.assertEqual((edge["target_id"], edge["source_id"]),
                                         (dependency, consumer))
                    self.assertIn(manifest["service_id"], impact["candidate_service_ids"])
                    self.assertEqual(impact["source"], "db/migrations/005_seed_acme.sql")
                    self.assertEqual(impact["observed_service_impact"], "UNKNOWN")
                    self.assertFalse(impact["causality_verified"])
                    self.assertFalse(impact["redundancy_evaluated"])
                    self.assertEqual(impact["tenant_scope"], "UNKNOWN")
                    self.assertIsNone(impact["observed_at"])
                    self.assertIsNone(impact["known_at"])
                    self.assertEqual(manifest["graph_version"], gen.SEED_GIT_BLOB)
                    self.assertEqual(manifest["catalog_sha256"], self.catalog_sha)
                    self.assertIsNone(manifest["tenant_id"])
                    self.assertIsNone(manifest["incident_id"])
                    self.assertIsNone(manifest["run_id"])
                    self.assertIsNone(manifest["ticket_id"])
                    self.assertEqual(manifest["evidence_ids"], [])
                    self.assertEqual(manifest["itil"]["priority_confirmed"], "UNKNOWN")
                    self.assertFalse(manifest["itil"]["roles_authenticated"])
                    self.assertFalse(manifest["publishable_to_core_or_glpi"])
                    self.assertFalse(manifest["live_effects_authorized"])
                    self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                                        for c in manifest["checkpoints"]))
                    events = manifest["events"]
                    self.assertEqual(len({e["source_event_id"] for e in events}), len(events))
                    self.assertEqual(len({e["correlation_key"] for e in events}), 1)
                    self.assertTrue(all(e["ci_id"] in self.graph["nodes"] and
                                        e["tenant_id"] is None and
                                        e["tenant_scope"] == "UNKNOWN" and
                                        e["provenance"] == "SYNTHETIC_FIXTURE" and
                                        e["freshness"] == "SYNTHETIC_CLOCK_ONLY"
                                        for e in events))

    def test_storyboard_projects_same_event_ids_path_roles_and_unknown_runtime(self):
        manifest = gen.replay(seed=20261018)
        story = gen.storyboard_offline(manifest)
        self.assertEqual(story, gen.storyboard_offline(gen.replay(seed=20261018)))
        self.assertEqual(story["source_dataset_sha256"], manifest["dataset_sha256"])
        self.assertEqual(story["source_manifest_sha256"],
                         hashlib.sha256(gen._canonical(manifest)).hexdigest())
        self.assertEqual(story["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual(story["service_id"], "ACME-SVC-PAYMENTS")
        self.assertEqual(story["dependency_path"]["node_ids"],
                         manifest["impact_estimate"]["path_node_ids"])
        self.assertEqual(story["dependency_path"]["edge_ids"],
                         manifest["impact_estimate"]["path_edge_ids"])
        self.assertEqual(story["dependency_path"]["business_links"], [
            {"edge_id": "ACME-E01", "business_ci_id": "ACME-BIZ-PAYMENTS"}])
        self.assertEqual(story["event_count"], 7)
        self.assertEqual([e["source_event_id"] for e in story["timeline"]],
                         [e["source_event_id"] for e in manifest["events"]])
        self.assertEqual([e["event_time"] for e in story["timeline"]],
                         [e["event_time"] for e in manifest["events"]])
        self.assertEqual([e["ci_id"] for e in story["timeline"]],
                         [e["ci_id"] for e in manifest["events"]])
        self.assertEqual([e["observed_at"] for e in story["timeline"]],
                         [e["observed_at"] for e in manifest["events"]])
        self.assertEqual([e["known_at"] for e in story["timeline"]],
                         [e["known_at"] for e in manifest["events"]])
        self.assertEqual([e["dedupe_key"] for e in story["timeline"]],
                         [e["dedupe_key"] for e in manifest["events"]])
        self.assertEqual({e["correlation_key"] for e in story["timeline"]},
                         {story["correlation_key"]})
        self.assertTrue(all(e["freshness"] == "SYNTHETIC_CLOCK_ONLY" and
                            e["tenant_scope"] == "UNKNOWN" for e in story["timeline"]))
        self.assertEqual(story["itil"]["roles_planned"], [
            "N1", "N2", "N3", "INCIDENT_COMMANDER"])
        self.assertEqual(story["itil"]["priority_candidate"], "P1")
        self.assertEqual(story["itil"]["priority_confirmed"], "UNKNOWN")
        self.assertFalse(story["itil"]["roles_authenticated"])
        self.assertEqual(story["dependency_path"]["observed_service_impact"], "UNKNOWN")
        for key in ("tenant_id", "incident_id", "run_id", "ticket_id"):
            self.assertIsNone(story[key])
        self.assertEqual(story["evidence_ids"], [])
        self.assertEqual(story["runtime_api_readback"], "NOT_EXECUTED")
        self.assertFalse(story["publishable_to_core_or_glpi"])
        self.assertFalse(story["live_effects_authorized"])
        self.assertFalse(story["recovery_verified"])
        self.assertTrue(all(e["runtime_evidence_id"] is None and
                            e["runtime_readback"] == "NOT_EXECUTED" and
                            e["provenance"] == "SYNTHETIC_FIXTURE"
                            for e in story["timeline"]))
        self.assertEqual([c["stage"] for c in story["checkpoints"]], list(gen.CHECKPOINTS))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in story["checkpoints"]))

    def test_storyboard_rejects_rehashed_forged_runtime_and_non_golden_mode(self):
        manifest = gen.replay()
        for name, mutate in (
            ("runtime_evidence", lambda m: m["events"][2].__setitem__("evidence_id", "FAKE")),
            ("recovered", lambda m: m["events"][-1]["payload"].__setitem__("state", "HEALTHY")),
            ("ticket", lambda m: m.__setitem__("ticket_id", "FAKE")),
            ("checkpoint", lambda m: m["checkpoints"][3].__setitem__("status", "SUCCESS")),
        ):
            with self.subTest(name=name):
                forged = copy.deepcopy(manifest)
                mutate(forged)
                unsigned = {k: v for k, v in forged.items() if k != "dataset_sha256"}
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(unsigned)).hexdigest()
                with self.assertRaises(ValueError):
                    gen.storyboard_offline(forged)
        with self.assertRaises(ValueError):
            gen.storyboard_offline(gen.replay(seed=20261019))
        capacity = gen.replay("CAPACITY_PRESSURE", seed=42, stochastic=True)
        self.assertEqual(gen.storyboard_offline(capacity)["event_count"], capacity["event_count"])
        fp = gen.replay("CAPACITY_PRESSURE", seed=42, false_positive=True)
        with self.assertRaises(ValueError):
            gen.storyboard_offline(fp)
        self.assertEqual(gen.storyboard_offline(fp, false_positive=True)["itil"]["priority_candidate"],
                         "UNKNOWN")

    def test_cli_storyboard_export_is_deterministic_and_not_runtime_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "acme-storyboard.json"
            cmd = [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
                   "--scenario", "REDUNDANT_SAN_PATH_LOSS", "--seed", "20261018",
                   "--storyboard", "--output", str(out)]
            first = subprocess.run(cmd, capture_output=True, text=True, check=True)
            raw = out.read_bytes()
            second = subprocess.run(cmd, capture_output=True, text=True, check=True)
            story = json.loads(raw)
            self.assertEqual(raw, out.read_bytes())
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(json.loads(first.stdout)["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(story, gen.storyboard_offline(gen.replay()))
            self.assertEqual(story["schema"], "aiops.acme.synthetic-storyboard.v1")
            self.assertEqual(story["runtime_api_readback"], "NOT_EXECUTED")
            self.assertFalse(story["publishable_to_core_or_glpi"])

    def test_cli_cannot_overwrite_source_fixture_or_file_alias(self):
        """Replay export must not mutate the pinned SQL/catalog or repository docs."""
        original = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (gen.SEED_FILE, gen.CATALOG_FILE)}
        with tempfile.TemporaryDirectory() as d:
            alias = Path(d) / "seed-symlink.json"
            alias.symlink_to(gen.SEED_FILE)
            hardlink = Path(d) / "seed-hardlink.json"
            hardlink.hardlink_to(gen.SEED_FILE)
            targets = (gen.SEED_FILE, gen.CATALOG_FILE,
                       gen.ROOT / "docs/customer-story/ACME-SYNTHETIC-INCIDENT-CATALOG-CONTRACT-2026-10-31.md",
                       alias, hardlink)
            for target in targets:
                with self.subTest(target=str(target)):
                    result = subprocess.run(
                        [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
                         "--scenario", "REDUNDANT_SAN_PATH_LOSS", "--seed", "20261018",
                         "--output", str(target)],
                        capture_output=True, text=True, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("refusing", result.stderr)
        for path, digest in original.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

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


class AcmeTwinSourcedServiceContextTests(unittest.TestCase):
    """Provenance-adversarial, offline-only Twin service context assertions."""

    def test_site_and_criticality_are_from_pinned_nodes_not_runtime(self):
        manifest = gen.replay(seed=20261018)
        context = gen.twin_service_context_offline(manifest)
        self.assertEqual(context["source_git_blob"], gen.SEED_GIT_BLOB)
        self.assertEqual(context["source"], "db/migrations/005_seed_acme.sql")
        self.assertEqual(context["site"], "PARIS")
        self.assertEqual(set(context["site_by_path_ci_id"]),
                         set(manifest["impact_estimate"]["path_node_ids"]))
        self.assertEqual(set(context["site_by_path_ci_id"].values()), {"PARIS"})
        self.assertEqual(context["service_criticality_synthetic_1_to_5"], 5)
        self.assertEqual(context["service_id"], "ACME-SVC-PAYMENTS")
        self.assertEqual(context["freshness"], "PINNED_FIXTURE_NOT_LIVE")

    def test_missing_dc_owner_sla_ola_team_change_and_maintenance_remain_unknown(self):
        context = gen.storyboard_offline(gen.replay())["twin_service_context"]
        for key in ("datacenter_id", "datacenter_relation", "service_owner_id",
                    "service_team_id", "sla_id", "ola_id", "change_id",
                    "maintenance_actual", "blast_radius_observed",
                    "impact_observed", "itil_priority_confirmed"):
            with self.subTest(key=key):
                self.assertEqual(context[key], "UNKNOWN")
        self.assertIsNone(context["maintenance_window_synthetic"])
        self.assertEqual(context["change_lookup"], "PLANNED_NOT_EXECUTED")
        self.assertEqual(context["runtime_readback"], "NOT_EXECUTED")
        self.assertEqual(context["tenant_scope"], "UNKNOWN")

    def test_dependency_blast_radius_and_priority_are_candidates_only(self):
        manifest = gen.replay()
        context = gen.twin_service_context_offline(manifest)
        impact = manifest["impact_estimate"]
        self.assertEqual(context["dependency_direction"], "REVERSE_CONSUMER_TO_DEPENDENCY")
        self.assertEqual(context["dependency_path_edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(context["dependency_path_node_ids"], impact["path_node_ids"])
        self.assertEqual(context["blast_radius_candidate_service_ids"],
                         ["ACME-SVC-ERP", "ACME-SVC-PAYMENTS"])
        self.assertEqual(context["blast_radius_candidate_ci_count"],
                         impact["candidate_ci_count"])
        self.assertEqual(context["impact_estimated"], "HIGH")
        self.assertEqual(context["urgency_synthetic"], "CRITICAL")
        self.assertEqual(context["itil_priority_candidate"], "P1")
        self.assertFalse(context["causality_verified"])
        self.assertFalse(context["redundancy_evaluated"])

    def test_forged_manifest_fields_cannot_claim_twin_or_runtime_provenance(self):
        original = gen.replay()
        for name, mutate in (
            ("service", lambda m: m.__setitem__("service_id", "ACME-SVC-ERP")),
            ("site", lambda m: m.__setitem__("site", "LONDON")),
            ("owner", lambda m: m.__setitem__("service_owner_id", "FAKE")),
            ("impact", lambda m: m["impact_estimate"].__setitem__(
                "candidate_service_ids", ["ACME-SVC-PAYMENTS"])),
            ("priority", lambda m: m["itil"].__setitem__("priority_confirmed", "P1")),
            ("evidence", lambda m: m.__setitem__("evidence_ids", ["FAKE"])),
        ):
            with self.subTest(name=name):
                forged = copy.deepcopy(original)
                mutate(forged)
                unsigned = {k: v for k, v in forged.items() if k != "dataset_sha256"}
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(unsigned)).hexdigest()
                with self.assertRaises(ValueError):
                    gen.twin_service_context_offline(forged)

    def test_tampered_seed_graph_rejected_and_replay_not_mutated(self):
        from unittest import mock
        manifest = gen.replay()
        before = gen._canonical(manifest)
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "005_seed_acme.sql"
            altered.write_bytes(gen.SEED_FILE.read_bytes().replace(
                b"'PARIS'", b"'LONDON'", 1))
            with mock.patch.object(gen, "SEED_FILE", altered):
                with self.assertRaises(ValueError):
                    gen.twin_service_context_offline(manifest)
        story = gen.storyboard_offline(manifest)
        self.assertEqual(gen._canonical(manifest), before)
        self.assertEqual(story["source_dataset_sha256"], manifest["dataset_sha256"])
        self.assertFalse(story["publishable_to_core_or_glpi"])
        self.assertEqual(story["checkpoints"], [
            {"stage": stage, "status": "NOT_EXECUTED", "id": None}
            for stage in gen.CHECKPOINTS
        ])



class AcmeTwinAuthorityBoundaryContractTests(unittest.TestCase):
    """Source-pinned Twin contract: synthetic facts are not runtime authority."""

    @classmethod
    def setUpClass(cls):
        cls.graph = gen.load_graph()
        cls.catalog, _ = gen.load_catalog()
        raw = gen.SEED_FILE.read_bytes()
        cls.seed_sha = gen._git_blob(raw)
        cls.node_rows = {
            node: {"site": site, "criticality": int(criticality)}
            for node, site, criticality in re.findall(
                r"^\('(ACME-[^']+)','(?:BUSINESS|SERVICE|APPLICATION|VM|SERVER|STORAGE|SAN|NETWORK|NAS)','[^']+','([^']+)','[^']+',([1-5]),",
                raw.decode("utf-8"), re.M)
        }

    def _supported(self):
        return [s for s in self.catalog["scenarios"]
                if s["status"] == "SUPPORTED_BY_SEED"]

    def test_all_supported_sites_and_service_criticality_are_pinned_node_facts(self):
        self.assertEqual(self.seed_sha, gen.SEED_GIT_BLOB)
        self.assertEqual(len(self.node_rows), 18)
        for scenario in self._supported():
            with self.subTest(scenario=scenario["key"]):
                manifest = gen.replay(scenario["key"], seed=20261018)
                context = gen.storyboard_offline(manifest)["twin_service_context"]
                nodes = manifest["impact_estimate"]["path_node_ids"]
                expected_sites = {ci: self.node_rows[ci]["site"] for ci in nodes}
                self.assertEqual(context["site_by_path_ci_id"], expected_sites)
                self.assertEqual(context["site"], next(iter(set(expected_sites.values())))
                                 if len(set(expected_sites.values())) == 1 else "UNKNOWN")
                self.assertEqual(context["service_criticality_synthetic_1_to_5"],
                                 self.node_rows[manifest["service_id"]]["criticality"])
                self.assertEqual(context["source_git_blob"], self.seed_sha)
                self.assertEqual(context["source"], "db/migrations/005_seed_acme.sql")
                self.assertEqual(context["freshness"], "PINNED_FIXTURE_NOT_LIVE")
                self.assertEqual(context["provenance"], "SYNTHETIC_FIXTURE")

    def test_absent_governance_authorities_never_become_contracts_or_assignments(self):
        absent = ("datacenter_id", "datacenter_relation", "service_owner_id",
                  "service_team_id", "sla_id", "ola_id", "change_id",
                  "maintenance_actual", "blast_radius_observed",
                  "impact_observed", "itil_priority_confirmed")
        for scenario in self._supported():
            with self.subTest(scenario=scenario["key"]):
                manifest = gen.replay(scenario["key"], seed=20261018)
                story = gen.storyboard_offline(manifest)
                context = story["twin_service_context"]
                for key in absent:
                    self.assertEqual(context[key], "UNKNOWN", key)
                self.assertEqual(context["maintenance_window_synthetic"],
                                 scenario["maintenance_window"])
                self.assertEqual(context["runtime_readback"], "NOT_EXECUTED")
                self.assertEqual(context["tenant_scope"], "UNKNOWN")
                self.assertIsNone(story["incident_id"])
                self.assertIsNone(story["run_id"])
                self.assertIsNone(story["ticket_id"])
                self.assertEqual(story["evidence_ids"], [])
                self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                                    for c in story["checkpoints"]))

    def test_blast_radius_is_independently_reverse_reachable_not_observed(self):
        for scenario in self._supported():
            with self.subTest(scenario=scenario["key"]):
                manifest = gen.replay(scenario["key"], seed=20261018)
                context = gen.twin_service_context_offline(manifest)
                reached = {manifest["ci_id"]}
                while True:
                    new = {edge["source_id"] for edge in self.graph["edges"].values()
                           if edge["target_id"] in reached}
                    if new <= reached:
                        break
                    reached |= new
                services = sorted(ci for ci in reached
                                  if self.graph["nodes"][ci]["type"] == "SERVICE")
                self.assertEqual(context["blast_radius_candidate_service_ids"], services)
                self.assertEqual(context["blast_radius_candidate_ci_count"], len(reached))
                self.assertEqual(context["dependency_direction"],
                                 "REVERSE_CONSUMER_TO_DEPENDENCY")
                nodes = context["dependency_path_node_ids"]
                for edge_id, dependency, consumer in zip(
                        context["dependency_path_edge_ids"], nodes, nodes[1:]):
                    edge = self.graph["edges"][edge_id]
                    self.assertEqual((edge["target_id"], edge["source_id"]),
                                     (dependency, consumer))
                criticality = max(self.graph["nodes"][ci]["criticality"]
                                  for ci in services)
                estimated = "HIGH" if criticality >= 5 else (
                    "MEDIUM" if criticality >= 3 else "LOW")
                self.assertEqual(context["impact_estimated"], estimated)
                self.assertEqual(context["itil_priority_candidate"],
                                 manifest["itil"]["priority_candidate"])
                self.assertEqual(context["impact_observed"], "UNKNOWN")
                self.assertEqual(context["itil_priority_confirmed"], "UNKNOWN")
                self.assertFalse(context["causality_verified"])
                self.assertFalse(context["redundancy_evaluated"])

    def test_maintenance_and_false_positive_do_not_authorize_itil_priority(self):
        scenario = next(s for s in self._supported()
                        if s["key"] == "APPLICATION_DEGRADATION")
        manifest = gen.replay(scenario["key"], seed=20261018)
        context = gen.twin_service_context_offline(manifest)
        self.assertEqual(context["maintenance_window_synthetic"],
                         {"start_offset_seconds": 0, "end_offset_seconds": 120})
        self.assertTrue(any(e["maintenance_window_active"] for e in manifest["events"]))
        self.assertEqual(context["itil_priority_candidate"], "UNKNOWN")
        self.assertEqual(context["maintenance_actual"], "UNKNOWN")
        self.assertEqual(context["change_lookup"], "NOT_PRESENT_IN_SCENARIO")
        self.assertEqual(context["itil_priority_confirmed"], "UNKNOWN")
        false_alarm = gen.replay("NETWORK_FAILURE", seed=20261018, false_positive=True)
        with self.assertRaises(ValueError):
            gen.twin_service_context_offline(false_alarm)
        noise = gen.twin_service_context_offline(false_alarm, false_positive=True)
        self.assertEqual(noise["itil_priority_candidate"], "UNKNOWN")
        self.assertEqual(noise["impact_observed"], "UNKNOWN")
        self.assertEqual(noise["maintenance_actual"], "UNKNOWN")

    def test_rehashed_forged_authorities_and_blast_radius_fail_closed(self):
        baseline = gen.replay(seed=20261018)
        for field, value in (
            ("site", "REMOTE"), ("datacenter_id", "FAKE-DC"),
            ("service_owner_id", "FAKE-OWNER"), ("service_team_id", "FAKE-TEAM"),
            ("sla_id", "FAKE-SLA"), ("ola_id", "FAKE-OLA"),
            ("change_id", "FAKE-CHANGE"), ("maintenance_actual", "APPROVED"),
            ("blast_radius_observed", ["ACME-SVC-PAYMENTS"]),
            ("impact_observed", "HIGH"), ("itil_priority_confirmed", "P1")
        ):
            with self.subTest(field=field):
                forged = copy.deepcopy(baseline)
                forged[field] = value
                unsigned = {k: v for k, v in forged.items() if k != "dataset_sha256"}
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(unsigned)).hexdigest()
                with self.assertRaises(ValueError):
                    gen.twin_service_context_offline(forged)
                with self.assertRaises(ValueError):
                    gen.storyboard_offline(forged)
        forged = copy.deepcopy(baseline)
        forged["impact_estimate"]["candidate_ci_count"] += 1
        with self.assertRaises(ValueError):
            gen.twin_service_context_offline(forged)

    def test_changed_seed_site_criticality_or_forged_owner_relation_is_rejected(self):
        baseline = gen.replay(seed=20261018)
        raw = gen.SEED_FILE.read_bytes()
        changes = (
            raw.replace(b"'PARIS'", b"'REMOTE'", 1),
            raw.replace(b"'HEALTHY',5,", b"'HEALTHY',4,", 1),
            raw + b"\n-- synthetic forged service_owner_id=FAKE\n",
        )
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            for i, changed in enumerate(changes):
                with self.subTest(mutation=i):
                    altered = Path(directory) / f"changed-{i}.sql"
                    altered.write_bytes(changed)
                    self.assertNotEqual(gen._git_blob(changed), gen.SEED_GIT_BLOB)
                    with self.assertRaisesRegex(ValueError, "seed graph Git blob mismatch"):
                        gen.load_graph(altered)
                    with mock.patch.object(gen, "SEED_FILE", altered):
                        with self.assertRaises(ValueError):
                            gen.twin_service_context_offline(baseline)
        self.assertEqual(gen.replay(seed=20261018), baseline)

    def test_golden_replay_bytes_are_unchanged_by_provenance_projection(self):
        baseline = gen.replay(seed=20261018)
        raw = (json.dumps(baseline, sort_keys=True, indent=2, ensure_ascii=True)
               + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        gen.storyboard_offline(baseline)
        self.assertEqual((json.dumps(baseline, sort_keys=True, indent=2,
                                     ensure_ascii=True) + "\n").encode("utf-8"), raw)
        self.assertEqual(baseline["seed"], 20261018)
        self.assertEqual(baseline["event_count"], 7)
        self.assertFalse(baseline["publishable_to_core_or_glpi"])



class AcmeTwinGovernanceSourceIndexTests(unittest.TestCase):
    """Independent pinned source pointers; absence must never become authority."""

    def test_index_is_pinned_to_graph_catalog_and_explicit_unknowns(self):
        index = gen.load_governance_source_index()
        self.assertEqual(gen._git_blob(gen.GOVERNANCE_SOURCE_FILE.read_bytes()),
                         gen.GOVERNANCE_SOURCE_GIT_BLOB)
        self.assertEqual(index["graph_git_blob"], gen.SEED_GIT_BLOB)
        self.assertEqual(index["catalog_git_blob"], gen.CATALOG_GIT_BLOB)
        self.assertEqual(index["provenance"], "SYNTHETIC_FIXTURE")
        self.assertEqual(index["tenant_scope"], "UNKNOWN")
        self.assertEqual(len(index["fields"]), 13)
        for field in ("datacenter_id", "datacenter_relation", "service_owner_id",
                      "service_team_id", "sla_id", "ola_id", "change_id",
                      "maintenance_actual"):
            with self.subTest(field=field):
                self.assertEqual(index["fields"][field],
                                 {"authority": "UNKNOWN", "source": None, "selector": None})

    def test_record_values_are_derived_from_pinned_sources_not_authority_claims(self):
        graph = gen.load_graph()
        catalog, _ = gen.load_catalog()
        for scenario in catalog["scenarios"]:
            if scenario["status"] != "SUPPORTED_BY_SEED":
                continue
            with self.subTest(scenario=scenario["key"]):
                manifest = gen.replay(scenario["key"], seed=20261018)
                context = gen.storyboard_offline(manifest)["twin_service_context"]
                records = context["governance_source_records"]
                self.assertEqual(context["governance_source_index_git_blob"],
                                 gen.GOVERNANCE_SOURCE_GIT_BLOB)
                self.assertEqual(set(records), set(gen.load_governance_source_index()["fields"]))
                for field, record in records.items():
                    self.assertEqual(record["value"], context[field])
                    self.assertEqual(record["provenance"], "SYNTHETIC_FIXTURE")
                    self.assertEqual(record["tenant_scope"], "UNKNOWN")
                    if record["authority"] == "UNKNOWN":
                        self.assertEqual(record["value"], "UNKNOWN")
                        self.assertIsNone(record["source"])
                        self.assertIsNone(record["source_git_blob"])
                        self.assertEqual(record["source_ci_ids"], [])
                site = records["site"]
                self.assertEqual(site["source_git_blob"], gen.SEED_GIT_BLOB)
                self.assertEqual(site["source_ci_ids"],
                                 manifest["impact_estimate"]["path_node_ids"])
                self.assertEqual(records["service_criticality_synthetic_1_to_5"][
                    "source_ci_ids"], [manifest["service_id"]])
                self.assertEqual(records["maintenance_window_synthetic"]["source_git_blob"],
                                 gen.CATALOG_GIT_BLOB)
                self.assertEqual(records["maintenance_window_synthetic"]["value"],
                                 scenario["maintenance_window"])
                self.assertEqual(records["blast_radius_candidate_service_ids"]["value"],
                                 sorted(ci for ci in graph["nodes"]
                                        if graph["nodes"][ci]["type"] == "SERVICE"
                                        and ci in manifest["impact_estimate"]["candidate_service_ids"]))
                self.assertEqual(context["blast_radius_observed"], "UNKNOWN")

    def test_change_lookup_and_maintenance_are_plans_not_real_changes(self):
        golden = gen.storyboard_offline(gen.replay())
        records = golden["twin_service_context"]["governance_source_records"]
        self.assertEqual(records["change_lookup"]["value"], "PLANNED_NOT_EXECUTED")
        self.assertEqual(records["change_lookup"]["source_git_blob"], gen.SEED_GIT_BLOB)
        self.assertIsNone(records["maintenance_window_synthetic"]["value"])
        self.assertEqual(records["change_id"]["value"], "UNKNOWN")
        self.assertEqual(records["maintenance_actual"]["value"], "UNKNOWN")
        app = gen.storyboard_offline(gen.replay("APPLICATION_DEGRADATION", seed=20261018))
        app_records = app["twin_service_context"]["governance_source_records"]
        self.assertEqual(app_records["maintenance_window_synthetic"]["value"],
                         {"start_offset_seconds": 0, "end_offset_seconds": 120})
        self.assertEqual(app_records["change_lookup"]["value"], "NOT_PRESENT_IN_SCENARIO")
        self.assertEqual(app_records["maintenance_actual"]["value"], "UNKNOWN")
        self.assertEqual(app["itil"]["priority_candidate"], "UNKNOWN")
        self.assertEqual(app["itil"]["priority_confirmed"], "UNKNOWN")

    def test_forged_index_authority_selector_and_provenance_fail_closed(self):
        from unittest import mock
        raw = gen.GOVERNANCE_SOURCE_FILE.read_bytes()
        for name, mutate in (
            ("owner", lambda d: d["fields"]["service_owner_id"].update(
                {"authority": "SYNTHETIC_NODE_ONLY", "source": "FAKE",
                 "selector": "fake.owner"})),
            ("sla", lambda d: d["fields"]["sla_id"].update(
                {"authority": "VERIFIED", "source": "FAKE", "selector": "fake.sla"})),
            ("maintenance", lambda d: d["fields"]["maintenance_window_synthetic"].update(
                {"authority": "APPROVED"})),
            ("graph", lambda d: d.__setitem__("graph_git_blob", "FAKE")),
            ("tenant", lambda d: d.__setitem__("tenant_scope", "ACME-TENANT-FAKE")),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                forged = json.loads(raw)
                mutate(forged)
                path = Path(directory) / "source-index.json"
                path.write_text(json.dumps(forged, sort_keys=True) + "\n",
                                encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "governance source index Git blob mismatch"):
                    gen.load_governance_source_index(path)
                with mock.patch.object(gen, "GOVERNANCE_SOURCE_FILE", path):
                    with self.assertRaises(ValueError):
                        gen.storyboard_offline(gen.replay())
        self.assertEqual(gen._git_blob(gen.GOVERNANCE_SOURCE_FILE.read_bytes()),
                         gen.GOVERNANCE_SOURCE_GIT_BLOB)

    def test_story_checkpoints_and_golden_replay_remain_reproducible(self):
        manifest = gen.replay(seed=20261018)
        raw = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True)
               + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        first = gen.storyboard_offline(manifest)
        self.assertEqual(first, gen.storyboard_offline(gen.replay(seed=20261018)))
        self.assertEqual(first["source_dataset_sha256"], manifest["dataset_sha256"])
        self.assertEqual([event["source_event_id"] for event in first["timeline"]],
                         [event["source_event_id"] for event in manifest["events"]])
        self.assertEqual(first["checkpoints"], [
            {"stage": stage, "status": "NOT_EXECUTED", "id": None}
            for stage in gen.CHECKPOINTS])
        self.assertIsNone(first["incident_id"])
        self.assertIsNone(first["run_id"])
        self.assertIsNone(first["ticket_id"])
        self.assertEqual(first["evidence_ids"], [])
        self.assertEqual(first["dependency_path"]["candidate_service_ids"],
                         ["ACME-SVC-ERP", "ACME-SVC-PAYMENTS"])
        self.assertEqual(first["dependency_path"]["observed_service_impact"], "UNKNOWN")
        self.assertFalse(first["recovery_verified"])
        self.assertEqual((json.dumps(manifest, sort_keys=True, indent=2,
                                     ensure_ascii=True) + "\n").encode("utf-8"), raw)



class AcmeSyntheticVerticalContractTests(unittest.TestCase):
    """No-effect ITIL storyboard: script anchors never become runtime receipts."""

    def setUp(self):
        self.manifest = gen.replay(seed=20261018)
        self.contract = gen.vertical_contract_offline(self.manifest)

    def test_vertical_fixture_is_independently_blob_pinned_and_graph_bound(self):
        fixture = gen.load_vertical_contract_fixture()
        self.assertEqual(gen._git_blob(gen.VERTICAL_CONTRACT_FILE.read_bytes()),
                         gen.VERTICAL_CONTRACT_GIT_BLOB)
        self.assertEqual(fixture["graph_git_blob"], gen.SEED_GIT_BLOB)
        self.assertEqual(fixture["governance_index_git_blob"],
                         gen.GOVERNANCE_SOURCE_GIT_BLOB)
        self.assertEqual(fixture["seed"], 20261018)
        self.assertEqual(len(fixture["stages"]), 15)
        steps = {n: action for n, _, action, _, _ in gen.load_graph()["steps"]}
        for stage in fixture["stages"]:
            self.assertEqual(stage["expected_action"], steps[stage["source_step"]])
            self.assertIn(stage["runtime_checkpoint"], (None, *gen.CHECKPOINTS))

    def test_vertical_projection_is_byte_deterministic_without_changing_replay(self):
        self.assertEqual(gen._canonical(self.contract),
                         gen._canonical(gen.vertical_contract_offline(gen.replay())))
        self.assertEqual(self.contract["source_dataset_sha256"],
                         self.manifest["dataset_sha256"])
        raw = (json.dumps(self.manifest, sort_keys=True, indent=2,
                          ensure_ascii=True) + "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(self.contract["source_event_ids"],
                         [e["source_event_id"] for e in self.manifest["events"]])
        with self.assertRaises(ValueError):
            gen.vertical_contract_offline(gen.replay(seed=20261019))

    def test_all_fifteen_stages_are_unexecuted_without_runtime_id_or_evidence(self):
        contract = self.contract
        self.assertEqual(contract["runtime_readback"], "NOT_EXECUTED")
        self.assertFalse(contract["publishable_to_core_or_glpi"])
        self.assertFalse(contract["live_effects_authorized"])
        self.assertFalse(contract["simulation_executed"])
        self.assertFalse(contract["post_action_verified"])
        self.assertFalse(contract["resolution_verified"])
        self.assertFalse(contract["reopen_verified"])
        for field in ("tenant_id", "ticket_id", "incident_id", "run_id"):
            self.assertIsNone(contract[field])
        self.assertEqual(contract["evidence_ids"], [])
        self.assertEqual([c["stage"] for c in contract["checkpoints"]],
                         list(gen.CHECKPOINTS))
        for checkpoint in contract["checkpoints"]:
            self.assertEqual(checkpoint, {"stage": checkpoint["stage"],
                                          "status": "NOT_EXECUTED", "id": None})
        for stage in contract["stages"]:
            self.assertEqual(stage["status"], "NOT_EXECUTED")
            self.assertIsNone(stage["runtime_id"])
            self.assertEqual(stage["runtime_evidence_ids"], [])
            self.assertFalse(stage["anchor_is_runtime_proof"])
            self.assertEqual(stage["source_authority"], "OFFLINE_SCRIPT_ONLY")
            self.assertEqual(stage["tenant_scope"], "UNKNOWN")

    def test_stage_anchors_match_exact_synthetic_event_ids_ci_and_times(self):
        events = self.manifest["events"]
        names = [stage["stage"] for stage in self.contract["stages"]]
        self.assertEqual(names[:5], ["EVENT_ALERT", "GLPI_TICKET", "CORE_INCIDENT",
                                     "CORE_RUN", "TWIN_IMPACT_CANDIDATE"])
        self.assertIn("ANALYST", names)
        self.assertIn("CRITIC", names)
        self.assertIn("HITL_APPROVAL", names)
        self.assertIn("SIMULATE", names)
        self.assertIn("REOPEN", names)
        for stage in self.contract["stages"]:
            event = events[stage["source_step"] - 1]
            self.assertEqual(stage["source_event_id"], event["source_event_id"])
            self.assertEqual(stage["source_event_time"], event["event_time"])
            self.assertEqual(stage["source_event_ci_id"], event["ci_id"])
            self.assertEqual(stage["source_action"], event["action"])
        self.assertEqual([e["at_seconds"] for e in events],
                         [0, 15, 30, 45, 60, 90, 110])

    def test_foreign_tenant_forged_source_and_fake_receipts_are_rejected(self):
        mutations = (
            ("foreign tenant", lambda m: m.__setitem__("tenant_id", "FOREIGN")),
            ("foreign scope", lambda m: m.__setitem__("tenant_scope", "TENANT-A")),
            ("fake incident", lambda m: m.__setitem__("incident_id", "INC-FAKE")),
            ("fake evidence", lambda m: m.__setitem__("evidence_ids", ["EVID-FAKE"])),
            ("forged source", lambda m: m["events"][0].__setitem__(
                "source_event_id", "SYN-EVT-FAKE")),
            ("false observation", lambda m: m["impact_estimate"].__setitem__(
                "observed_service_impact", "CONFIRMED")),
            ("false priority", lambda m: m["itil"].__setitem__(
                "priority_confirmed", "P1")),
            ("stale time", lambda m: m["events"][0].__setitem__(
                "known_at", "2026-11-01T10:00:00Z")),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                forged = copy.deepcopy(self.manifest)
                mutate(forged)
                with self.assertRaises(ValueError):
                    gen.vertical_contract_offline(forged)

    def test_forged_contract_stage_tenant_source_and_runtime_checkpoint_rejected(self):
        original = gen.load_vertical_contract_fixture()
        mutations = (
            ("foreign tenant", lambda d: d.__setitem__("tenant_scope", "TENANT-B")),
            ("false execution", lambda d: d.__setitem__("execution_status", "SUCCESS")),
            ("fake authority", lambda d: d.__setitem__("authority", "CORE_VERIFIED")),
            ("forged source", lambda d: d.__setitem__("source", "untrusted.sql")),
            ("wrong event", lambda d: d["stages"][0].__setitem__("source_step", 7)),
            ("wrong action", lambda d: d["stages"][0].__setitem__(
                "expected_action", "VERIFY")),
            ("fake checkpoint", lambda d: d["stages"][0].__setitem__(
                "runtime_checkpoint", "EVIDENCE-FAKE")),
            ("bool step", lambda d: d["stages"][0].__setitem__("source_step", True)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                forged = copy.deepcopy(original)
                mutate(forged)
                with self.assertRaisesRegex(ValueError, "untrusted vertical contract override"):
                    gen.vertical_contract_offline(self.manifest, fixture=forged)
                path = Path(directory) / "forged-vertical.json"
                path.write_text(json.dumps(forged) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "vertical contract Git blob mismatch"):
                    gen.load_vertical_contract_fixture(path)

    def test_candidate_blast_radius_and_governance_unknowns_remain_separate(self):
        contract = self.contract
        self.assertEqual(contract["dependency_path"]["edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(contract["dependency_path"]["candidate_service_ids"],
                         ["ACME-SVC-ERP", "ACME-SVC-PAYMENTS"])
        self.assertEqual(contract["dependency_path"]["observed_service_impact"], "UNKNOWN")
        self.assertFalse(contract["dependency_path"]["causality_verified"])
        self.assertEqual(contract["observed_impact"], "UNKNOWN")
        self.assertEqual(contract["itil"]["priority_candidate"], "P1")
        self.assertEqual(contract["itil"]["priority_confirmed"], "UNKNOWN")
        self.assertEqual(contract["governance_source_records"]["site"]["value"], "PARIS")
        self.assertEqual(contract["governance_source_records"][
            "service_criticality_synthetic_1_to_5"]["value"], 5)
        self.assertEqual(set(contract["governance_unknowns"]), {
            "datacenter_id", "datacenter_relation", "service_owner_id",
            "service_team_id", "sla_id", "ola_id", "change_id", "maintenance_actual"})
        self.assertTrue(all(v == "UNKNOWN" for v in contract["governance_unknowns"].values()))
        self.assertEqual(contract["analyst_hypothesis"], "UNKNOWN")
        self.assertEqual(contract["critic_disposition"], "UNKNOWN")
        self.assertEqual(contract["policy_decision"], "UNKNOWN")
        self.assertEqual(contract["hitl_approval"], "UNKNOWN")

    def test_cli_vertical_export_is_readonly_and_storyboard_mode_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "vertical-contract.json"
            cmd = [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
                   "--seed", "20261018", "--vertical-contract",
                   "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(gen._canonical(parsed), gen._canonical(self.contract))
            self.assertEqual(parsed["event_count"], 7)
            self.assertEqual(json.loads(result.stdout)["sha256"],
                             hashlib.sha256(output.read_bytes()).hexdigest())
            exclusive = subprocess.run(cmd + ["--storyboard"],
                                       capture_output=True, text=True)
            self.assertNotEqual(exclusive.returncode, 0)
            self.assertIn("exclusive", exclusive.stderr)


class AcmeSyntheticEventImpactContractTests(unittest.TestCase):
    """No runtime writes: source-pinned Event->correlation->Twin candidate only."""

    def setUp(self):
        self.replay = gen.replay(seed=20261018)
        self.fixture = gen.load_event_impact_contract_fixture()
        self.contract = gen.event_impact_contract_offline(self.replay)

    def test_independent_blob_and_golden_seed_are_pinned(self):
        raw = gen.EVENT_IMPACT_CONTRACT_FILE.read_bytes()
        self.assertEqual(gen._git_blob(raw), gen.EVENT_IMPACT_CONTRACT_GIT_BLOB)
        self.assertEqual(self.fixture["source_dataset_sha256"], self.replay["dataset_sha256"])
        self.assertEqual(self.fixture["graph_git_blob"], gen.SEED_GIT_BLOB)
        self.assertEqual(self.fixture["vertical_contract_git_blob"], gen.VERTICAL_CONTRACT_GIT_BLOB)
        self.assertEqual(len(self.fixture["events"]), 7)
        self.assertEqual((len(gen.load_graph()["nodes"]), len(gen.load_graph()["edges"])), (18, 17))

    def test_correlation_and_dedup_are_fixture_local_not_itil_incident(self):
        events = self.replay["events"]
        correlation = self.contract["correlation"]
        self.assertEqual(correlation["key"], self.fixture["correlation_key"])
        self.assertEqual(correlation["scope"], "LOCAL_FIXTURE_ONLY")
        self.assertEqual(correlation["event_count"], 7)
        self.assertEqual(correlation["ci_ids"], sorted({e["ci_id"] for e in events}))
        self.assertEqual(correlation["dedupe_keys"], [e["dedupe_key"] for e in events])
        self.assertEqual(len(set(correlation["dedupe_keys"])), 7)
        self.assertEqual(correlation["runtime_incident_id"], None)
        self.assertEqual(self.contract["source_event_ids"],
                         [e["source_event_id"] for e in events])
        self.assertTrue(all(e["runtime_readback"] == "NOT_EXECUTED"
                            for e in self.contract["timeline"]))

    def test_reverse_reachable_services_and_path_are_candidates_not_outages(self):
        graph = gen.load_graph()
        independent = gen.dependency_candidates(graph, self.replay["ci_id"],
                                                self.replay["service_id"])
        candidate = self.contract["blast_radius_candidate"]
        self.assertEqual(candidate["candidate_service_ids"],
                         independent["candidate_service_ids"])
        self.assertEqual(candidate["candidate_ci_count"],
                         independent["candidate_ci_count"])
        self.assertEqual(candidate["path_edge_ids"], ["ACME-E08", "ACME-E06",
                                                       "ACME-E04", "ACME-E02"])
        self.assertEqual(candidate["path_node_ids"], independent["path_node_ids"])
        self.assertEqual(candidate["classification"], "REVERSE_REACHABLE_CANDIDATE_ONLY")
        self.assertEqual(candidate["observed_service_impact"], "UNKNOWN")
        self.assertIsNone(candidate["observed_at"])
        self.assertFalse(candidate["causality_verified"])
        self.assertFalse(candidate["redundancy_evaluated"])
        self.assertEqual(self.contract["itil"]["priority_candidate"], "P1")
        self.assertEqual(self.contract["itil"]["priority_confirmed"], "UNKNOWN")
        self.assertEqual(self.contract["itil"]["impact_observed"], "UNKNOWN")

    def test_every_source_time_is_pinned_and_known_at_is_simulated(self):
        self.assertEqual([e["event_time"] for e in self.contract["timeline"]],
                         [e["event_time"] for e in self.fixture["events"]])
        for projected, original in zip(self.contract["timeline"], self.replay["events"]):
            self.assertEqual(projected["source_event_id"], original["source_event_id"])
            self.assertEqual(projected["known_at"], original["known_at"])
            self.assertEqual(projected["ci_id"], original["ci_id"])
            self.assertEqual(projected["action"], original["action"])
            self.assertEqual(projected["provenance"], "SYNTHETIC_FIXTURE")
        self.assertEqual(self.contract["runtime_readback"], "NOT_EXECUTED")

    def test_no_forged_glpi_run_evidence_model_effect_or_itil_receipt(self):
        for key in ("tenant_id", "ticket_id", "incident_id", "run_id",
                    "analyst_receipt", "critic_receipt", "policy_receipt",
                    "hitl_receipt", "simulation_receipt"):
            self.assertIsNone(self.contract[key], key)
        self.assertEqual(self.contract["evidence_ids"], [])
        self.assertEqual(self.contract["tenant_scope"], "UNKNOWN")
        self.assertFalse(self.contract["publishable_to_core_or_glpi"])
        self.assertFalse(self.contract["live_effects_authorized"])
        self.assertEqual(len(self.contract["stages"]), 15)
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["runtime_id"] is None and
                            s["runtime_evidence_ids"] == []
                            for s in self.contract["stages"]))
        self.assertEqual(len(self.contract["checkpoints"]), 6)
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in self.contract["checkpoints"]))
        self.assertTrue(all(v == "UNKNOWN" for v in
                            self.contract["governance_unknowns"].values()))

    def test_foreign_tenant_seed_and_timestamp_rehash_fail_closed(self):
        cases = [
            ("tenant_id", "foreign-tenant"),
            ("tenant_scope", "tenant-authorized"),
            ("seed", 20261019),
            ("seed", True),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                forged = copy.deepcopy(self.replay)
                forged[field] = value
                forged["dataset_sha256"] = hashlib.sha256(gen._canonical(
                    {k: v for k, v in forged.items() if k != "dataset_sha256"}
                )).hexdigest()
                with self.assertRaises(ValueError):
                    gen.event_impact_contract_offline(forged)
        for field, value in (("event_time", "2026-10-31T09:42:01Z"),
                             ("known_at", "2026-10-31T09:41:59Z"),
                             ("observed_at", "2026-10-31T09:42:05Z")):
            with self.subTest(time_field=field):
                forged = copy.deepcopy(self.replay)
                forged["events"][0][field] = value
                with self.assertRaises(ValueError):
                    gen.event_impact_contract_offline(forged)

    def test_forged_source_event_dedupe_and_impact_are_rejected(self):
        for field, value in (
            ("source_event_id", "SYN-EVT-AAAAAAAAAAAAAAAAAAAA"),
            ("dedupe_key", "SYN-DEDUP-AAAAAAAAAAAAAAAAAAAA"),
            ("correlation_key", "SYN-CORR-AAAAAAAAAAAAAAAAAAAA"),
            ("ci_id", "ACME-SAN-FABRIC-B"),
            ("evidence_id", "forged-receipt"),
        ):
            with self.subTest(field=field):
                forged = copy.deepcopy(self.replay)
                forged["events"][1][field] = value
                with self.assertRaises(ValueError):
                    gen.event_impact_contract_offline(forged)
        forged = copy.deepcopy(self.replay)
        forged["impact_estimate"]["candidate_service_ids"] = ["ACME-SVC-PAYMENTS"]
        with self.assertRaises(ValueError):
            gen.event_impact_contract_offline(forged)

    def test_forged_fixture_source_tenant_bool_and_blast_radius_fail_closed(self):
        for mutate in (
            lambda f: f.update(tenant_scope="ACME"),
            lambda f: f.update(seed=True),
            lambda f: f["events"][0].update(event_time="2026-10-31T09:42:01Z"),
            lambda f: f["events"][0].update(source_event_id="SYN-EVT-FAKE"),
            lambda f: f["blast_radius_candidate"].update(
                observed_service_impact="OUTAGE"),
            lambda f: f["blast_radius_candidate"].update(
                candidate_service_ids=["ACME-SVC-PAYMENTS"]),
        ):
            forged = copy.deepcopy(self.fixture)
            mutate(forged)
            with self.assertRaises(ValueError):
                gen.event_impact_contract_offline(self.replay, fixture=forged)
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "event-impact.json"
            bad.write_text(json.dumps(self.fixture).replace(
                '"tenant_scope": "UNKNOWN"', '"tenant_scope": "ACME"'),
                encoding="utf-8")
            with self.assertRaises(ValueError):
                gen.load_event_impact_contract_fixture(bad)

    def test_reproducible_cli_and_byte_identical_canonical_replay(self):
        before = json.dumps(self.replay, sort_keys=True, indent=2,
                            ensure_ascii=True) + "\n"
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(gen._canonical(self.contract),
                         gen._canonical(gen.event_impact_contract_offline(
                             gen.replay(seed=20261018))))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "event-impact.json"
            cmd = [sys.executable, str(gen.ROOT / "tools/generate_acme_incidents.py"),
                   "--seed", "20261018", "--event-impact-contract",
                   "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(gen._canonical(json.loads(output.read_text())),
                             gen._canonical(self.contract))
            self.assertEqual(json.loads(result.stdout)["sha256"],
                             hashlib.sha256(output.read_bytes()).hexdigest())
            exclusive = subprocess.run(cmd + ["--vertical-contract"],
                                       capture_output=True, text=True)
            self.assertNotEqual(exclusive.returncode, 0)
            self.assertIn("exclusive", exclusive.stderr)
        after = json.dumps(gen.replay(seed=20261018), sort_keys=True,
                           indent=2, ensure_ascii=True) + "\n"
        self.assertEqual(before, after)



class AcmeSyntheticIngestionPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = gen.replay(seed=20261018)

    def test_seven_events_and_fifteen_unexecuted_stages(self):
        r = ingest.ingestion_preflight_offline(self.manifest)
        self.assertEqual((r["source_event_count"], r["delivery_count"],
                          r["duplicate_delivery_count"]), (7, 7, 0))
        self.assertEqual(len(r["itil_stages"]), 15)
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and s["runtime_id"] is None
                            for s in r["itil_stages"]))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in r["checkpoints"]))
        self.assertFalse(r["publishable_to_core_or_glpi"])
        self.assertFalse(r["content_hash_is_evidence_receipt"])

    def test_hash_provenance_and_no_runtime_ids(self):
        r = ingest.ingestion_preflight_offline(self.manifest)
        self.assertEqual(r["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual(r["event_impact_contract_git_blob"],
                         gen.EVENT_IMPACT_CONTRACT_GIT_BLOB)
        for e, c in zip(self.manifest["events"], r["local_delivery_checks"]):
            self.assertEqual(c["content_digest_sha256"],
                             hashlib.sha256(gen._canonical(e)).hexdigest())
        i = r["candidate_incident"]
        self.assertEqual(i["status"], "NOT_CREATED")
        self.assertTrue(all(i[k] is None for k in ("incident_id", "run_id", "ticket_id")))
        self.assertEqual(i["evidence_ids"], [])
        self.assertIsNone(r["tenant_id"])
        self.assertEqual(r["tenant_scope"], "UNKNOWN")
        self.assertEqual(i["priority_confirmed"], "UNKNOWN")
        self.assertEqual(i["observed_impact"], "UNKNOWN")
        self.assertEqual(r["blast_radius_candidate"]["path_edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertFalse(r["blast_radius_candidate"]["causality_verified"])

    def test_exact_duplicate_delivery_is_deduped(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows.extend((copy.deepcopy(rows[0]), copy.deepcopy(rows[2])))
        r = ingest.ingestion_preflight_offline(self.manifest, deliveries=rows)
        self.assertEqual((r["delivery_count"], r["source_event_count"],
                          r["duplicate_delivery_count"]), (9, 7, 2))
        self.assertEqual([c["delivery_count"] for c in r["local_delivery_checks"]],
                         [2, 1, 2, 1, 1, 1, 1])
        self.assertEqual(r["candidate_incident"]["status"], "NOT_CREATED")

    def test_cross_partition_and_foreign_partition_fail_closed(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows[1]["test_partition"] = "SYNTHETIC_TEST_PARTITION_B"
        with self.assertRaisesRegex(ValueError, "cross-partition"):
            ingest.ingestion_preflight_offline(self.manifest, deliveries=rows)
        for bad in ("FOREIGN", "ACME", "", None, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ingest.ingestion_preflight_offline(self.manifest, test_partition=bad)

    def test_partition_isolation_does_not_claim_tenant_authority(self):
        a = ingest.ingestion_preflight_offline(self.manifest)
        b = ingest.ingestion_preflight_offline(
            self.manifest, test_partition="SYNTHETIC_TEST_PARTITION_B")
        self.assertNotEqual(a["test_partition"], b["test_partition"])
        self.assertFalse(a["test_partition_is_tenant_authority"])
        self.assertFalse(b["test_partition_is_tenant_authority"])
        self.assertIsNone(a["tenant_id"])
        self.assertIsNone(b["tenant_id"])
        self.assertEqual(a["candidate_incident"]["source_event_ids"],
                         b["candidate_incident"]["source_event_ids"])

    def test_forged_source_ci_tenant_dedupe_payload_and_evidence_rejected(self):
        mutations = (("source", "FORGED"), ("ci_id", "FORGED"),
                     ("tenant_id", "FAKE_TENANT"), ("tenant_scope", "VERIFIED"),
                     ("dedupe_key", "FAKE"), ("correlation_key", "FAKE"),
                     ("evidence_id", "FAKE"), ("payload", {"fake": True}))
        for field, value in mutations:
            with self.subTest(field=field):
                rows = ingest.synthetic_deliveries_offline(self.manifest)
                rows[0]["event"][field] = value
                with self.assertRaises(ValueError):
                    ingest.ingestion_preflight_offline(self.manifest, deliveries=rows)

    def test_forged_seed_digest_and_source_timestamp_rejected(self):
        for field, value in (("seed", 20261019), ("dataset_sha256", "0" * 64)):
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                manifest[field] = value
                with self.assertRaises(ValueError):
                    ingest.ingestion_preflight_offline(manifest)
        for field, value in (("event_time", "2026-10-31T09:42:01Z"),
                             ("known_at", "2026-10-31T10:42:00Z"),
                             ("source", "FORGED")):
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                manifest["events"][0][field] = value
                with self.assertRaises(ValueError):
                    ingest.ingestion_preflight_offline(manifest)

    def test_stale_future_and_non_utc_delivery_rejected(self):
        for stamp in ("2026-10-31T10:00:00Z", "2026-10-31T09:41:00Z",
                      "2026-10-31T09:42:02+00:00", "not-a-time"):
            with self.subTest(stamp=stamp):
                rows = ingest.synthetic_deliveries_offline(self.manifest)
                rows[0]["synthetic_received_at"] = stamp
                with self.assertRaises(ValueError):
                    ingest.ingestion_preflight_offline(self.manifest, deliveries=rows)

    def test_conflicting_duplicate_missing_and_foreign_digest_rejected(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        with self.assertRaises(ValueError):
            ingest.ingestion_preflight_offline(self.manifest, deliveries=rows[:-1])
        bad = copy.deepcopy(rows)
        bad.append(copy.deepcopy(bad[0]))
        bad[-1]["event"]["payload"] = {"fake": True}
        with self.assertRaises(ValueError):
            ingest.ingestion_preflight_offline(self.manifest, deliveries=bad)
        bad = copy.deepcopy(rows)
        bad[0]["source_dataset_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            ingest.ingestion_preflight_offline(self.manifest, deliveries=bad)

    def test_determinism_and_canonical_replay_sha(self):
        before = json.dumps(self.manifest, sort_keys=True, indent=2,
                            ensure_ascii=True) + "\n"
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        a = ingest.ingestion_preflight_offline(self.manifest)
        b = ingest.ingestion_preflight_offline(gen.replay(seed=20261018))
        self.assertEqual(gen._canonical(a), gen._canonical(b))
        self.assertEqual(before, json.dumps(gen.replay(seed=20261018),
                                            sort_keys=True, indent=2,
                                            ensure_ascii=True) + "\n")



class AcmeSyntheticItilReplayVerifierTests(unittest.TestCase):
    """Source-anchored 15-stage projection, never a runtime ITIL receipt."""

    @classmethod
    def setUpClass(cls):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        cls.verifier = verifier
        cls.manifest = gen.replay(seed=20261018)

    def test_fifteen_stages_anchor_to_seven_pinned_events(self):
        result = self.verifier.verify_itil_replay_offline(self.manifest)
        self.assertEqual((len(result["stages"]), result["source_event_count"]), (15, 7))
        self.assertEqual(len(result["checkpoints"]), 6)
        self.assertEqual(result["source_event_ids"],
                         [e["source_event_id"] for e in self.manifest["events"]])
        for stage in result["stages"]:
            source = self.manifest["events"][stage["source_step"] - 1]
            self.assertEqual(stage["source_event_id"], source["source_event_id"])
            self.assertEqual(stage["source_event_time"], source["event_time"])
            self.assertEqual(stage["source_known_at"], source["known_at"])
            self.assertEqual(stage["source_ci_id"], source["ci_id"])
            self.assertEqual(stage["source_dedupe_key"], source["dedupe_key"])
            self.assertEqual(stage["status"], "NOT_EXECUTED")
            self.assertEqual(stage["source_anchor_validation"],
                             "MATCHED_PINNED_SYNTHETIC_EVENT")
            self.assertFalse(stage["source_anchor_is_runtime_proof"])
            self.assertIsNone(stage["runtime_id"])
            self.assertEqual(stage["runtime_evidence_ids"], [])

    def test_runtime_receipts_and_authorities_are_never_inferred(self):
        result = self.verifier.verify_itil_replay_offline(self.manifest)
        self.assertEqual(result["runtime_readback"], "NOT_EXECUTED")
        self.assertEqual(result["tenant_scope"], "UNKNOWN")
        self.assertIsNone(result["tenant_id"])
        self.assertFalse(result["test_partition_is_tenant_authority"])
        self.assertTrue(all(v is None or v == [] for v in result["runtime_receipts"].values()))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in result["checkpoints"]))
        self.assertEqual(result["priority_confirmed"], "UNKNOWN")
        self.assertEqual(result["observed_impact"], "UNKNOWN")
        self.assertFalse(result["source_content_hash_is_evidence_receipt"])
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])

    def test_reverse_twin_candidate_and_governance_are_sourced_not_observed(self):
        result = self.verifier.verify_itil_replay_offline(self.manifest)
        impact = result["blast_radius_candidate"]
        self.assertEqual(impact["path_edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(impact["candidate_service_ids"],
                         ["ACME-SVC-ERP", "ACME-SVC-PAYMENTS"])
        self.assertEqual(impact["classification"], "REVERSE_REACHABLE_CANDIDATE_ONLY")
        self.assertFalse(impact["causality_verified"])
        self.assertEqual(impact["observed_service_impact"], "UNKNOWN")
        self.assertTrue(all(v == "UNKNOWN" for v in result["governance_unknowns"].values()))

    def test_reproducible_projection_and_canonical_replay_file_sha(self):
        first = self.verifier.verify_itil_replay_offline(self.manifest)
        second = self.verifier.verify_itil_replay_offline(gen.replay(seed=20261018),
                                                          candidate=first)
        self.assertEqual(gen._canonical(first), gen._canonical(second))
        replay_bytes = (json.dumps(self.manifest, sort_keys=True, indent=2,
                                   ensure_ascii=True) + "\n").encode()
        self.assertEqual(hashlib.sha256(replay_bytes).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(first["canonical_replay_file_sha256"],
                         hashlib.sha256(replay_bytes).hexdigest())

    def test_duplicate_deliveries_remain_local_without_incident_creation(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows.extend((copy.deepcopy(rows[0]), copy.deepcopy(rows[3])))
        result = self.verifier.verify_itil_replay_offline(self.manifest, deliveries=rows)
        self.assertEqual((result["delivery_count"], result["duplicate_delivery_count"]),
                         (9, 2))
        self.assertEqual(result["candidate_incident"]["status"], "NOT_CREATED")
        self.assertIsNone(result["candidate_incident"]["incident_id"])

    def test_cross_partition_delivery_and_projection_are_rejected(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows[0]["test_partition"] = "SYNTHETIC_TEST_PARTITION_B"
        with self.assertRaises(ValueError):
            self.verifier.verify_itil_replay_offline(self.manifest, deliveries=rows)
        foreign = self.verifier.verify_itil_replay_offline(
            self.manifest, test_partition="SYNTHETIC_TEST_PARTITION_B")
        with self.assertRaisesRegex(ValueError, "untrusted synthetic ITIL replay projection"):
            self.verifier.verify_itil_replay_offline(self.manifest, candidate=foreign)
        for partition in ("TENANT-REAL", "", True, None):
            with self.subTest(partition=partition), self.assertRaises(ValueError):
                self.verifier.verify_itil_replay_offline(self.manifest,
                                                         test_partition=partition)

    def test_stale_future_and_non_utc_deliveries_fail_closed(self):
        for stamp in ("2026-10-31T10:00:00Z", "2026-10-31T09:41:00Z",
                      "2026-10-31T09:42:02+00:00", "INVALID"):
            with self.subTest(stamp=stamp):
                rows = ingest.synthetic_deliveries_offline(self.manifest)
                rows[0]["synthetic_received_at"] = stamp
                with self.assertRaises(ValueError):
                    self.verifier.verify_itil_replay_offline(self.manifest, deliveries=rows)

    def test_foreign_tenant_seed_source_and_known_at_fail_closed(self):
        for label, mutate in (
            ("tenant", lambda m: m.__setitem__("tenant_id", "FORGED")),
            ("seed", lambda m: m.__setitem__("seed", 20261019)),
            ("source", lambda m: m["events"][0].__setitem__("source", "FORGED")),
            ("known_at", lambda m: m["events"][0].__setitem__(
                "known_at", "2026-10-31T10:42:00Z")),
            ("ci", lambda m: m["events"][0].__setitem__("ci_id", "FOREIGN-CI")),
            ("correlation", lambda m: m["events"][0].__setitem__(
                "correlation_key", "FAKE")),
        ):
            with self.subTest(label=label):
                forged = copy.deepcopy(self.manifest)
                mutate(forged)
                with self.assertRaises(ValueError):
                    self.verifier.verify_itil_replay_offline(forged)

    def test_forged_runtime_receipts_stage_and_blast_radius_fail_closed(self):
        good = self.verifier.verify_itil_replay_offline(self.manifest)
        for label, mutate in (
            ("glpi", lambda p: p["runtime_receipts"].__setitem__(
                "glpi_ticket_id", "GLPI-FAKE")),
            ("evidence", lambda p: p["runtime_receipts"].__setitem__(
                "evidence_ids", ["EVID-FAKE"])),
            ("stage", lambda p: p["stages"][5].__setitem__("status", "SUCCESS")),
            ("model", lambda p: p["runtime_receipts"].__setitem__(
                "analyst_output", {"model": "FAKE"})),
            ("impact", lambda p: p["blast_radius_candidate"].__setitem__(
                "observed_service_impact", "CONFIRMED")),
            ("priority", lambda p: p.__setitem__("priority_confirmed", "P1")),
            ("checkpoint", lambda p: p["checkpoints"][0].__setitem__(
                "id", "RUN-FAKE")),
            ("type-alias", lambda p: p.__setitem__("source_event_count", True)),
        ):
            with self.subTest(label=label):
                forged = copy.deepcopy(good)
                mutate(forged)
                with self.assertRaisesRegex(ValueError, "untrusted synthetic ITIL replay projection"):
                    self.verifier.verify_itil_replay_offline(self.manifest, candidate=forged)

    def test_missing_or_conflicting_delivery_never_becomes_receipt(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        with self.assertRaises(ValueError):
            self.verifier.verify_itil_replay_offline(self.manifest, deliveries=rows[:-1])
        rows.append(copy.deepcopy(rows[0]))
        rows[-1]["event"]["source_event_id"] = "FORGED"
        with self.assertRaises(ValueError):
            self.verifier.verify_itil_replay_offline(self.manifest, deliveries=rows)


class AcmeSyntheticReceiptReconciliationTests(unittest.TestCase):
    """Read-only contract: synthetic absence is never a Core receipt."""

    @classmethod
    def setUpClass(cls):
        from tools import acme_synthetic_receipt_reconciliation as receipts
        cls.receipts = receipts
        cls.manifest = gen.replay(seed=20261018)

    def test_fifteen_stages_and_six_checkpoints_remain_unexecuted(self):
        result = self.receipts.reconcile_fixture_receipts_offline(self.manifest)
        self.assertEqual((len(result["stages"]), len(result["checkpoints"])), (15, 6))
        self.assertEqual(result["reconciliation_status"], "NO_AUTHENTICATED_READBACK")
        self.assertEqual(result["runtime_readback"], "NOT_EXECUTED")
        self.assertEqual(result["tenant_scope"], "UNKNOWN")
        self.assertFalse(result["test_partition_is_tenant_authority"])
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["receipt_id"] is None and not s["receipt_verified"]
                            for s in result["stages"]))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and c["id"] is None
                            for c in result["checkpoints"]))
        self.assertTrue(all(v is None or v == [] for v in
                            result["runtime_references"].values()))
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])

    def test_replay_hash_seed_and_graph_are_preserved(self):
        result = self.receipts.reconcile_fixture_receipts_offline(self.manifest)
        self.assertEqual(result["seed"], 20261018)
        self.assertEqual(result["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual(result["canonical_replay_file_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(result["source_event_count"], 7)
        self.assertEqual(result["blast_radius_candidate"]["path_edge_ids"],
                         ["ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02"])
        self.assertEqual(result["observed_impact"], "UNKNOWN")
        self.assertEqual(result["priority_confirmed"], "UNKNOWN")
        self.assertEqual(gen._canonical(result), gen._canonical(
            self.receipts.reconcile_fixture_receipts_offline(
                gen.replay(seed=20261018), candidate=result)))

    def test_stage_authority_requirements_do_not_become_receipts(self):
        result = self.receipts.reconcile_fixture_receipts_offline(self.manifest)
        stages = {s["stage"]: s for s in result["stages"]}
        self.assertEqual(stages["GLPI_TICKET"]["required_authority"],
                         "GLPI_AUTHENTICATED_READBACK")
        self.assertEqual(stages["CORE_RUN"]["required_authority"],
                         "CORE_AUTHENTICATED_READBACK")
        self.assertEqual(stages["EVIDENCE"]["required_authority"],
                         "IMMUTABLE_EVIDENCE_SERVICE")
        self.assertEqual(stages["HITL_APPROVAL"]["required_authority"],
                         "CORE_VERIFIED_HUMAN_LEDGER")
        self.assertEqual(stages["SIMULATE"]["required_authority"],
                         "ISOLATED_EXECUTOR_RECEIPT")
        for stage in result["stages"]:
            self.assertEqual(stage["receipt_source"], "UNKNOWN")
            self.assertIsNone(stage["receipt_observed_at"])
            self.assertIn(stage["source_event_id"], result["source_event_ids"])

    def test_test_only_absence_envelope_never_claims_core_readback(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        verified = verifier.verify_itil_replay_offline(self.manifest)
        envelope = self.receipts.synthetic_absence_envelope_offline(verified)
        result = self.receipts.reconcile_fixture_receipts_offline(
            self.manifest, absence_envelope=envelope)
        self.assertTrue(result["absence_envelope_checked"])
        self.assertFalse(result["absence_envelope_is_core_receipt"])
        self.assertEqual(result["runtime_readback"], "NOT_EXECUTED")
        self.assertEqual(result["reconciliation_status"], "NO_AUTHENTICATED_READBACK")

    def test_foreign_partition_and_tenant_are_rejected(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        verified = verifier.verify_itil_replay_offline(self.manifest)
        base = self.receipts.synthetic_absence_envelope_offline(verified)
        for field, value in (("test_partition", "SYNTHETIC_TEST_PARTITION_B"),
                             ("tenant_id", "FORGED-TENANT"),
                             ("source", "CORE_AUTHENTICATED_READBACK")):
            with self.subTest(field=field):
                changed = copy.deepcopy(base)
                changed[field] = value
                with self.assertRaises(ValueError):
                    self.receipts.reconcile_fixture_receipts_offline(
                        self.manifest, absence_envelope=changed)

    def test_foreign_replay_seed_graph_and_event_refs_are_rejected(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        verified = verifier.verify_itil_replay_offline(self.manifest)
        base = self.receipts.synthetic_absence_envelope_offline(verified)
        for field, value in (("source_manifest_sha256", "0" * 64),
                             ("source_dataset_sha256", "1" * 64),
                             ("graph_version", "FORGED-GRAPH"),
                             ("source_event_ids", ["FORGED-EVENT"]),
                             ("ci_id", "FOREIGN-CI"),
                             ("service_id", "FOREIGN-SERVICE")):
            with self.subTest(field=field):
                changed = copy.deepcopy(base)
                changed[field] = value
                with self.assertRaises(ValueError):
                    self.receipts.reconcile_fixture_receipts_offline(
                        self.manifest, absence_envelope=changed)
        forged = copy.deepcopy(self.manifest)
        forged["seed"] = 20261019
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(forged)

    def test_stale_future_invalid_and_non_utc_readback_clocks_rejected(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        base = self.receipts.synthetic_absence_envelope_offline(
            verifier.verify_itil_replay_offline(self.manifest))
        for stamp in ("2026-10-31T10:00:00Z", "2026-10-31T09:41:00Z",
                      "2026-10-31T09:44:00+00:00", "INVALID", True):
            with self.subTest(stamp=stamp):
                changed = copy.deepcopy(base)
                changed["synthetic_checked_at"] = stamp
                with self.assertRaises(ValueError):
                    self.receipts.reconcile_fixture_receipts_offline(
                        self.manifest, absence_envelope=changed)

    def test_forged_incident_run_glpi_and_evidence_receipts_rejected(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        base = self.receipts.synthetic_absence_envelope_offline(
            verifier.verify_itil_replay_offline(self.manifest))
        for field, value in (("incident_id", "FORGED-INCIDENT"),
                             ("run_id", "FORGED-RUN"),
                             ("glpi_ticket_id", "FORGED-GLPI"),
                             ("evidence_ids", ["FORGED-EVIDENCE"]),
                             ("stage_receipts", [{"stage": "HITL_APPROVAL", "approved": True}])):
            with self.subTest(field=field):
                changed = copy.deepcopy(base)
                changed[field] = value
                with self.assertRaisesRegex(ValueError, "unverified runtime receipt"):
                    self.receipts.reconcile_fixture_receipts_offline(
                        self.manifest, absence_envelope=changed)

    def test_missing_or_extra_readback_fields_fail_closed(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        base = self.receipts.synthetic_absence_envelope_offline(
            verifier.verify_itil_replay_offline(self.manifest))
        missing = copy.deepcopy(base)
        del missing["source_event_ids"]
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(
                self.manifest, absence_envelope=missing)
        extra = copy.deepcopy(base)
        extra["actor_subject"] = "FORGED"
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(
                self.manifest, absence_envelope=extra)

    def test_forged_verified_projection_and_cross_partition_rejected(self):
        good = self.receipts.reconcile_fixture_receipts_offline(self.manifest)
        for field, value in (("reconciliation_status", "VERIFIED"),
                             ("runtime_readback", "SUCCESS"),
                             ("priority_confirmed", "P1"),
                             ("observed_impact", "HIGH"),
                             ("test_partition", "SYNTHETIC_TEST_PARTITION_B")):
            with self.subTest(field=field):
                changed = copy.deepcopy(good)
                changed[field] = value
                with self.assertRaisesRegex(ValueError, "untrusted receipt reconciliation"):
                    self.receipts.reconcile_fixture_receipts_offline(
                        self.manifest, candidate=changed)
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(
                self.manifest, test_partition="REAL-TENANT")

    def test_stale_or_cross_partition_delivery_rejected_before_reconciliation(self):
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows[0]["test_partition"] = "SYNTHETIC_TEST_PARTITION_B"
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(
                self.manifest, deliveries=rows)
        rows = ingest.synthetic_deliveries_offline(self.manifest)
        rows[0]["synthetic_received_at"] = "2026-10-31T10:00:00Z"
        with self.assertRaises(ValueError):
            self.receipts.reconcile_fixture_receipts_offline(
                self.manifest, deliveries=rows)



from unittest import mock


class AcmeCoreReadOnlyBindingProbeTests(unittest.TestCase):
    """All IDs below are TEST_ONLY hints, never observed Core receipts."""

    @classmethod
    def setUpClass(cls):
        from tools import acme_synthetic_core_binding_probe as probe
        cls.probe = probe
        cls.manifest = gen.replay()
        cls.now = datetime(2026, 11, 1, 8, 59, tzinfo=timezone.utc)
        cls.rid = "RUN-TEST-ONLY-UNTRUSTED"
        cls.iid = "INC-TEST-ONLY-UNTRUSTED"

    def _responses(self):
        run = {
            "run_id": self.rid, "incident_id": self.iid,
            "scenario_id": "SCN-GOLDEN-PAYMENT-P1",
            "mode": "DEMO", "status": "CREATED",
            "created_at": "2026-11-01T08:58:00Z",
        }
        return {
            "/api/runs": {"items": [copy.deepcopy(run)]},
            "/api/runs/" + self.rid: {
                "run": copy.deepcopy(run), "events": [
                    {"sequence": 1, "event_type": "RUN_CREATED",
                     "stage": "INGEST", "status": "CREATED",
                     "payload": {"scenario_id": "SCN-GOLDEN-PAYMENT-P1",
                                 "mode": "DEMO"}, "evidence_ids": []}]},
            "/api/noc/runs/" + self.rid: {
                "run": {k: run[k] for k in
                        ("run_id", "incident_id", "mode", "status")},
                "data_classification": "SYNTHETIC_CANONICAL_RUN",
                "tenant_acl_qualified": False,
                "runtime_authenticated": False,
                "live_remediation_authorized": False},
        }

    def _call(self, data=None, **kwargs):
        data = self._responses() if data is None else data
        calls = []
        def fake_get(base, path, token=None):
            calls.append((base, path, token))
            return copy.deepcopy(data[path])
        params = dict(origin="https://core.example",
                      expected_run_id=self.rid,
                      expected_incident_id=self.iid,
                      token="TEST_ONLY_NOT_A_SECRET",
                      now=self.now, get=fake_get)
        params.update(kwargs)
        with mock.patch.dict("os.environ", {
                "AIOPS_ACME_TRUSTED_CORE_ORIGINS": "https://core.example"}):
            result = self.probe.probe_core_binding_readonly(self.manifest, **params)
        return result, calls

    def test_internal_bearer_pair_never_promotes_tenant_actor_or_itil_receipts(self):
        result, calls = self._call()
        self.assertEqual(result["result"], "UNKNOWN")
        self.assertEqual(result["reason"],
                         "TENANT_ACTOR_AND_CANONICAL_EVENT_BINDING_UNAVAILABLE")
        self.assertTrue(result["core_internal_pair_match"])
        self.assertEqual(result["core_read_attempt_count"], 3)
        self.assertEqual([bool(t) for _, _, t in calls], [False, False, True])
        self.assertEqual(len(result["stages"]), 15)
        self.assertEqual(len(result["checkpoints"]), 6)
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["receipt_id"] is None for s in result["stages"]))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and
                            c["id"] is None for c in result["checkpoints"]))
        self.assertIsNone(result["run_id"])
        self.assertIsNone(result["incident_id"])
        self.assertIsNone(result["tenant_id"])
        self.assertIsNone(result["actor_subject"])
        self.assertEqual(result["evidence_ids"], [])
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["source_event_binding_verified"])
        self.assertEqual(result["canonical_replay_file_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertNotIn("TEST_ONLY_NOT_A_SECRET", str(result))

    def test_missing_ids_or_token_never_initiates_core_request(self):
        for params, reason in (
                ({"expected_run_id": None}, "EXPECTED_CORE_PAIR_UNKNOWN"),
                ({"expected_incident_id": None}, "EXPECTED_CORE_PAIR_UNKNOWN"),
                ({"expected_run_id": "RUN-../bad"}, "EXPECTED_CORE_PAIR_UNKNOWN"),
                ({"token": None}, "INTERNAL_TOKEN_NOT_CONFIGURED")):
            with self.subTest(params=params):
                result, calls = self._call(**params)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(calls, [])

    def test_unpinned_or_credentialed_origin_does_not_forward_bearer(self):
        for origin in ("https://evil.example", "https://user@core.example",
                       "http://core.example", "https://core.example.evil.test",
                       "https://core.example/other"):
            with self.subTest(origin=origin):
                result, calls = self._call(origin=origin)
                self.assertEqual(result["reason"], "CORE_ORIGIN_NOT_PINNED")
                self.assertEqual(calls, [])

    def test_foreign_or_ambiguous_incident_run_registry_fails_closed(self):
        for mutation in (
                lambda d: d["/api/runs"]["items"][0].update(
                    incident_id="INC-FOREIGN-TEST"),
                lambda d: d["/api/runs"]["items"].append(
                    copy.deepcopy(d["/api/runs"]["items"][0])),
                lambda d: d["/api/runs"].update(items=[]),
                lambda d: d["/api/runs"]["items"][0].update(
                    scenario_id="SCN-OTHER")):
            data = self._responses()
            mutation(data)
            result, _ = self._call(data)
            self.assertIn(result["reason"], (
                "RUN_NOT_UNIQUELY_IN_REGISTRY_WINDOW",
                "RUN_REGISTRY_SCOPE_OR_SCENARIO_MISMATCH"))
            self.assertFalse(result["core_internal_pair_match"])

    def test_foreign_detail_and_internal_run_rejected(self):
        for path, field, value in (
                ("/api/runs/" + self.rid, "incident_id", "INC-FOREIGN-TEST"),
                ("/api/noc/runs/" + self.rid, "run_id", "RUN-FOREIGN-TEST")):
            data = self._responses()
            data[path]["run"][field] = value
            result, _ = self._call(data)
            self.assertIn(result["reason"], (
                "RUN_DETAIL_SCOPE_MISMATCH", "INTERNAL_PROJECTION_UNQUALIFIED"))
            self.assertFalse(result["core_internal_pair_match"])

    def test_missing_and_stale_core_timestamp_fail_closed(self):
        for stamp in (None, "2026-10-29T08:58:00Z",
                      "2026-11-01T09:10:00Z", "2026-11-01T08:58:00",
                      True):
            data = self._responses()
            data["/api/runs"]["items"][0]["created_at"] = stamp
            data["/api/runs/" + self.rid]["run"]["created_at"] = stamp
            result, _ = self._call(data)
            self.assertEqual(result["reason"], "RUN_SOURCE_TIMESTAMP_STALE_OR_MISSING")

    def test_forged_tenant_actor_or_runtime_authentication_claims_rejected(self):
        for target, field, value in (
                ("registry", "tenant_id", "TENANT-FORGED"),
                ("detail", "actor_subject", "actor-forged"),
                ("internal", "actor_verified", True),
                ("internal", "tenant_acl_qualified", True),
                ("internal", "runtime_authenticated", True)):
            data = self._responses()
            obj = (data["/api/runs"]["items"][0] if target == "registry"
                   else data["/api/runs/" + self.rid]["run"] if target == "detail"
                   else data["/api/noc/runs/" + self.rid])
            obj[field] = value
            result, _ = self._call(data)
            self.assertFalse(result["core_internal_pair_match"])
            self.assertEqual(result["result"], "UNKNOWN")

    def test_wrong_creation_event_or_foreign_nested_run_rejected(self):
        for field, value in (("event_type", "FAKE_EVENT"),
                             ("run_id", "RUN-FOREIGN-TEST")):
            data = self._responses()
            data["/api/runs/" + self.rid]["events"][0][field] = value
            result, _ = self._call(data)
            self.assertIn(result["reason"], (
                "RUN_CREATION_ANCHOR_MISMATCH", "RUN_EVENTS_UNQUALIFIED"))

    def test_foreign_partition_or_seed_cannot_become_core_binding(self):
        with self.assertRaises(ValueError):
            self._call(test_partition="REAL_TENANT")
        forged = copy.deepcopy(self.manifest)
        forged["seed"] = 20261019
        with mock.patch.dict("os.environ", {
                "AIOPS_ACME_TRUSTED_CORE_ORIGINS": "https://core.example"}):
            with self.assertRaises(ValueError):
                self.probe.probe_core_binding_readonly(
                    forged, origin="https://core.example",
                    expected_run_id=self.rid,
                    expected_incident_id=self.iid,
                    token="TEST_ONLY_NOT_A_SECRET")

    def test_missing_core_read_and_source_event_link_remain_unknown(self):
        data = self._responses()
        del data["/api/noc/runs/" + self.rid]
        result, calls = self._call(data)
        self.assertEqual(result["reason"], "CORE_READ_UNAVAILABLE")
        self.assertEqual(len(calls), 3)
        self.assertFalse(result["source_event_binding_verified"])
        self.assertIsNone(result["glpi_ticket_id"])



class AcmeFutureCoreActorTenantBindingTests(unittest.TestCase):
    """Only TEST_ONLY in-memory proposals; never independently authorized Core."""

    @classmethod
    def setUpClass(cls):
        from tools import acme_synthetic_future_core_binding as future
        cls.future = future
        cls.manifest = gen.replay()
        cls.now = datetime(2026, 11, 1, 9, 56, tzinfo=timezone.utc)

    def _proposal(self):
        from tools import acme_synthetic_itil_replay_verifier as verifier
        v = verifier.verify_itil_replay_offline(self.manifest)
        return {
            "schema": self.future.SCHEMA,
            "source": self.future.SOURCE,
            "test_partition": "SYNTHETIC_TEST_PARTITION_A",
            "principal": {
                "tenant_id": "TEST_ONLY_TENANT_A",
                "actor_subject": "TEST_ONLY_ACTOR_A",
            },
            "core": {
                "incident_id": "INC-TEST-ONLY-A",
                "run_id": "RUN-TEST-ONLY-A",
                "incident_tenant_id": "TEST_ONLY_TENANT_A",
                "run_tenant_id": "TEST_ONLY_TENANT_A",
                "incident_actor_subject": "TEST_ONLY_ACTOR_A",
                "run_actor_subject": "TEST_ONLY_ACTOR_A",
                "scenario_id": v["scenario_id"],
                "service_id": v["service_id"],
                "ci_id": v["ci_id"],
                "source_dataset_sha256": v["source_dataset_sha256"],
                "source_manifest_sha256": v["source_manifest_sha256"],
                "canonical_replay_file_sha256": v["canonical_replay_file_sha256"],
                "graph_version": v["graph_version"],
                "correlation_key": v["correlation"]["key"],
                "source_event_bindings": self.future.pinned_event_bindings(self.manifest),
                "readback_at": "2026-11-01T09:55:00Z",
            },
            "attestation": {
                "kind": "UNVERIFIED_TEST_INPUT",
                "actor_authenticated": False,
                "tenant_acl_qualified": False,
                "core_signature_verified": False,
            },
        }

    def test_absent_core_authority_is_unavailable_not_a_runtime_receipt(self):
        result = self.future.verify_future_core_binding_offline(
            self.manifest, now=self.now)
        self.assertEqual(result["result"], "UNAVAILABLE")
        self.assertEqual(result["runtime_readback"], "NOT_EXECUTED")
        self.assertFalse(result["proposal_shape_checked"])
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["actor_authenticated"])
        self.assertEqual(len(result["required_independent_authority"]), 6)
        self.assertEqual(result["canonical_replay_file_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")

    def test_matching_test_shape_cannot_attest_actor_tenant_or_run(self):
        proposal = self._proposal()
        result = self.future.verify_future_core_binding_offline(
            self.manifest, proposal=proposal, now=self.now)
        self.assertTrue(result["proposal_shape_checked"])
        self.assertEqual(result["result"], "UNAVAILABLE")
        self.assertEqual(result["reason"],
                         "TEST_SHAPE_MATCH_ONLY_INDEPENDENT_AUTHORITY_UNAVAILABLE")
        for key in ("tenant_id", "actor_subject", "incident_id", "run_id",
                    "glpi_ticket_id"):
            self.assertIsNone(result[key], key)
        self.assertEqual(result["evidence_ids"], [])
        self.assertFalse(result["source_event_binding_verified_by_core"])
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["runtime_id"] is None for s in result["stages"]))
        self.assertEqual(len(result["stages"]), 15)
        self.assertEqual(len(result["checkpoints"]), 6)
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and
                            c["id"] is None for c in result["checkpoints"]))
        self.assertNotIn("INC-TEST-ONLY-A", str(result))
        self.assertEqual(result, self.future.verify_future_core_binding_offline(
            self.manifest, proposal=proposal, now=self.now))

    def test_seven_hashes_are_independently_derived_from_canonical_events(self):
        rows = self.future.pinned_event_bindings(self.manifest)
        self.assertEqual(len(rows), 7)
        for event, row in zip(self.manifest["events"], rows):
            self.assertEqual(row["source_event_id"], event["source_event_id"])
            self.assertEqual(row["source_event_content_sha256"],
                             hashlib.sha256(gen._canonical(event)).hexdigest())
            self.assertEqual(row["dedupe_key"], event["dedupe_key"])
            self.assertEqual(row["event_time"], event["event_time"])

    def test_foreign_or_reordered_source_event_hashes_fail_closed(self):
        for change in ("digest", "drop", "reorder", "duplicate", "foreign_ci"):
            with self.subTest(change=change):
                proposal = self._proposal()
                rows = proposal["core"]["source_event_bindings"]
                if change == "digest":
                    rows[0]["source_event_content_sha256"] = "0" * 64
                elif change == "drop":
                    rows.pop()
                elif change == "reorder":
                    rows.reverse()
                elif change == "duplicate":
                    rows[1] = copy.deepcopy(rows[0])
                else:
                    rows[0]["ci_id"] = "FOREIGN-CI"
                with self.assertRaisesRegex(ValueError, "foreign replay"):
                    self.future.verify_future_core_binding_offline(
                        self.manifest, proposal=proposal, now=self.now)

    def test_foreign_tenant_or_actor_on_either_core_record_fails_closed(self):
        for key, value in (
            ("incident_tenant_id", "TEST_ONLY_TENANT_B"),
            ("run_tenant_id", "TEST_ONLY_TENANT_B"),
            ("incident_actor_subject", "TEST_ONLY_ACTOR_B"),
            ("run_actor_subject", "TEST_ONLY_ACTOR_B"),
        ):
            with self.subTest(key=key):
                proposal = self._proposal()
                proposal["core"][key] = value
                with self.assertRaisesRegex(ValueError, "foreign actor or tenant"):
                    self.future.verify_future_core_binding_offline(
                        self.manifest, proposal=proposal, now=self.now)

    def test_test_partition_is_not_a_tenant_authentication(self):
        proposal = self._proposal()
        proposal["test_partition"] = "SYNTHETIC_TEST_PARTITION_B"
        with self.assertRaisesRegex(ValueError, "foreign partition"):
            self.future.verify_future_core_binding_offline(
                self.manifest, proposal=proposal, now=self.now)
        with self.assertRaises(ValueError):
            self.future.verify_future_core_binding_offline(
                self.manifest, test_partition="REAL_CUSTOMER", now=self.now)

    def test_stale_future_missing_and_non_utc_readback_clock_fail_closed(self):
        for stamp in ("2026-11-01T09:40:00Z", "2026-11-01T10:00:00Z",
                      "2026-11-01T09:55:00+00:00", "not-a-clock", None, True):
            with self.subTest(stamp=stamp):
                proposal = self._proposal()
                proposal["core"]["readback_at"] = stamp
                with self.assertRaises(ValueError):
                    self.future.verify_future_core_binding_offline(
                        self.manifest, proposal=proposal, now=self.now)

    def test_untrusted_source_or_claimed_authority_is_rejected(self):
        for mutate in (
            lambda p: p.update(source="CORE_AUTHENTICATED"),
            lambda p: p["attestation"].update(actor_authenticated=True),
            lambda p: p["attestation"].update(tenant_acl_qualified=True),
            lambda p: p["attestation"].update(core_signature_verified=True),
            lambda p: p["attestation"].update(signed_receipt="FORGED"),
        ):
            proposal = self._proposal()
            mutate(proposal)
            with self.assertRaises(ValueError):
                self.future.verify_future_core_binding_offline(
                    self.manifest, proposal=proposal, now=self.now)

    def test_runtime_looking_or_missing_identifiers_never_promoted(self):
        for key, value in (
            ("incident_id", "INC-12345"),
            ("run_id", "RUN-12345"),
            ("incident_id", None),
            ("run_id", ""),
        ):
            with self.subTest(key=key, value=value):
                proposal = self._proposal()
                proposal["core"][key] = value
                with self.assertRaisesRegex(ValueError, "TEST_ONLY placeholder"):
                    self.future.verify_future_core_binding_offline(
                        self.manifest, proposal=proposal, now=self.now)

    def test_forged_seed_dataset_graph_correlation_or_scenario_fails(self):
        for key, value in (
            ("source_dataset_sha256", "0" * 64),
            ("source_manifest_sha256", "0" * 64),
            ("graph_version", "FORGED-GRAPH"),
            ("correlation_key", "FOREIGN-CORRELATION"),
            ("scenario_id", "SCN-FOREIGN"),
            ("service_id", "FOREIGN-SERVICE"),
        ):
            with self.subTest(key=key):
                proposal = self._proposal()
                proposal["core"][key] = value
                with self.assertRaisesRegex(ValueError, "foreign replay"):
                    self.future.verify_future_core_binding_offline(
                        self.manifest, proposal=proposal, now=self.now)
        forged = copy.deepcopy(self.manifest)
        forged["seed"] = 20261019
        with self.assertRaises(ValueError):
            self.future.verify_future_core_binding_offline(
                forged, now=self.now)

    def test_missing_and_extra_fields_fail_closed(self):
        for mutate in (
            lambda p: p["core"].pop("source_event_bindings"),
            lambda p: p["principal"].pop("actor_subject"),
            lambda p: p.update(evidence_ids=["FORGED"]),
            lambda p: p["core"].update(verified=True),
        ):
            proposal = self._proposal()
            mutate(proposal)
            with self.assertRaises(ValueError):
                self.future.verify_future_core_binding_offline(
                    self.manifest, proposal=proposal, now=self.now)

    def test_canonical_replay_stable_and_no_glpi_evidence_or_effect(self):
        before = (json.dumps(self.manifest, sort_keys=True, indent=2,
                             ensure_ascii=True) + "\n").encode()
        self.assertEqual(hashlib.sha256(before).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        result = self.future.verify_future_core_binding_offline(
            self.manifest, now=self.now)
        self.assertEqual(result["observed_impact"], "UNKNOWN")
        self.assertEqual(result["priority_confirmed"], "UNKNOWN")
        self.assertFalse(result["source_hash_is_evidence_receipt"])
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])
        self.assertEqual(result["blast_radius_candidate"]["classification"],
                         "REVERSE_REACHABLE_CANDIDATE_ONLY")

if __name__ == "__main__":
    unittest.main()



class AcmeCoreSingleEventHashGapTests(unittest.TestCase):
    """Core v1 is one source_payload_hash; ACME pins seven full-event hashes."""

    @classmethod
    def setUpClass(cls):
        from tools import acme_synthetic_core_event_hash_gap as gap
        cls.gap = gap
        cls.manifest = gen.replay()
        cls.now = 1793520000  # synthetic clock only, not observed Core time

    def _proposal(self, index=0):
        row = self.gap.pinned_hash_domains(self.manifest)[index]
        return {
            "schema": self.gap.CORE_SCHEMA,
            "source": self.gap.TEST_SOURCE,
            "test_partition": "SYNTHETIC_TEST_PARTITION_A",
            "tenant_id": "TEST_ONLY_TENANT_A",
            "actor_subject": "TEST_ONLY_ACTOR_A",
            "source_event_id": row["source_event_id"],
            "source_event_hash": row["local_payload_sha256_candidate"],
            "source_event_content_sha256": row["full_event_sha256"],
            "hash_scope": self.gap.HASH_SCOPE,
            "observed_at": self.now - 30,
            "known_at": self.now - 20,
            "expires_at": self.now + 60,
            "revoked": False,
            "verified": False,
            "authority": "UNVERIFIED_SYNTHETIC_PROJECTION",
        }

    def _verify(self, proposals=None, **kwargs):
        return self.gap.verify_single_event_core_gap_offline(
            self.manifest, proposals=proposals, now=self.now, **kwargs)

    def test_absent_core_source_is_explicitly_unavailable(self):
        result = self._verify()
        self.assertEqual(result["result"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "NO_INDEPENDENT_CORE_READBACK")
        self.assertEqual(result["synthetic_shape_coverage"], 0)
        self.assertEqual(result["core_readback_cardinality"],
                         "ONE_SOURCE_EVENT_PER_RESPONSE")
        self.assertFalse(result["core_hash_semantics_qualified"])

    def test_seven_hash_domains_are_recomputed_not_core_receipts(self):
        rows = self.gap.pinned_hash_domains(self.manifest)
        self.assertEqual(len(rows), 7)
        self.assertEqual(len({r["source_event_id"] for r in rows}), 7)
        for row, event in zip(rows, self.manifest["events"]):
            self.assertEqual(row["full_event_sha256"],
                             hashlib.sha256(gen._canonical(event)).hexdigest())
            self.assertEqual(row["local_payload_sha256_candidate"],
                             hashlib.sha256(gen._canonical(event["payload"])).hexdigest())
            self.assertNotEqual(row["full_event_sha256"],
                                row["local_payload_sha256_candidate"])
        self.assertFalse(self._verify()["local_payload_digest_is_core_receipt"])

    def test_one_or_seven_test_shapes_never_promote_core_authority(self):
        for count in (1, 7):
            with self.subTest(count=count):
                result = self._verify([self._proposal(i) for i in range(count)])
                self.assertEqual(result["synthetic_shape_coverage"], count)
                self.assertEqual(result["result"], "UNAVAILABLE")
                self.assertFalse(result["source_event_binding_verified_by_core"])
                self.assertEqual(result["reason"],
                                 "CORE_V1_SINGLE_EVENT_COVERAGE_ONLY" if count == 1
                                 else "SEVEN_TEST_SHAPES_ARE_NOT_CORE_AUTHORITY")
                self.assertIsNone(result["run_id"])
                self.assertIsNone(result["incident_id"])

    def test_foreign_tenant_actor_and_partition_are_rejected(self):
        for key, value in (("tenant_id", "TEST_ONLY_TENANT_B"),
                           ("actor_subject", "TEST_ONLY_ACTOR_B"),
                           ("test_partition", "SYNTHETIC_TEST_PARTITION_B")):
            proof = self._proposal()
            proof[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self._verify([proof])
        with self.assertRaises(ValueError):
            self._verify(expected_actor="idp|real-actor")

    def test_foreign_duplicate_reordered_and_missing_event_fail_closed(self):
        first = self._proposal(0)
        first["source_event_id"] = "FORGED-EVENT"
        with self.assertRaisesRegex(ValueError, "foreign source event"):
            self._verify([first])
        with self.assertRaisesRegex(ValueError, "duplicate or reordered"):
            self._verify([self._proposal(0), self._proposal(0)])
        with self.assertRaisesRegex(ValueError, "duplicate or reordered"):
            self._verify([self._proposal(2), self._proposal(1)])
        missing = self._proposal()
        del missing["source_event_hash"]
        with self.assertRaisesRegex(ValueError, "missing or unexpected"):
            self._verify([missing])

    def test_swapped_hash_domains_and_forged_digests_are_rejected(self):
        for field, replacement in (
                ("source_event_hash", self._proposal()["source_event_content_sha256"]),
                ("source_event_content_sha256", self._proposal()["source_event_hash"]),
                ("hash_scope", "CORE_VERIFIED_FULL_EVENT"),
                ("source_event_hash", "0" * 64)):
            proof = self._proposal()
            proof[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "hash domain mismatch"):
                self._verify([proof])

    def test_stale_future_expired_and_revoked_proposals_fail_closed(self):
        for field, value in (("observed_at", self.now - 301),
                             ("known_at", self.now + 1),
                             ("expires_at", self.now),
                             ("expires_at", self.now + 301),
                             ("observed_at", True),
                             ("revoked", True), ("verified", True)):
            proof = self._proposal()
            proof[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self._verify([proof])

    def test_forged_core_source_schema_or_runtime_receipt_rejected(self):
        for field, value in (("source", "CORE_CANONICAL_READBACK"),
                             ("schema", "aiops.core-actor-run-event-binding.v2"),
                             ("authority", "INDEPENDENTLY_VERIFIED")):
            proof = self._proposal()
            proof[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self._verify([proof])
        proof = self._proposal()
        proof["run_id"] = "RUN-FAKE"
        with self.assertRaisesRegex(ValueError, "unexpected synthetic"):
            self._verify([proof])

    def test_forged_replay_seed_or_event_payload_rejected(self):
        for field, value in (("seed", 20261019), ("scenario_id", "SCN-FAKE")):
            forged = copy.deepcopy(self.manifest)
            forged[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.gap.verify_single_event_core_gap_offline(forged, now=self.now)
        forged = copy.deepcopy(self.manifest)
        forged["events"][0]["payload"] = {"invented": "LIVE"}
        with self.assertRaises(ValueError):
            self.gap.verify_single_event_core_gap_offline(forged, now=self.now)

    def test_replay_digest_stages_and_checkpoints_remain_unchanged(self):
        result = self._verify([self._proposal()])
        self.assertEqual(result["canonical_replay_file_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual(result["seed"], 20261018)
        self.assertEqual(len(result["stages"]), 15)
        self.assertEqual(len(result["checkpoints"]), 6)
        self.assertTrue(all(s["status"] == "NOT_EXECUTED" and
                            s["runtime_id"] is None for s in result["stages"]))
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" and
                            c["id"] is None for c in result["checkpoints"]))
        self.assertEqual(result["observed_impact"], "UNKNOWN")
        self.assertEqual(result["priority_confirmed"], "UNKNOWN")
        self.assertEqual(result["evidence_ids"], [])
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])
        self.assertEqual(result, self._verify([self._proposal()]))
