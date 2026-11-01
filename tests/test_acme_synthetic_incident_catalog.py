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
                r"^\\('(ACME-[^']+)','(?:BUSINESS|SERVICE|APPLICATION|VM|SERVER|STORAGE|SAN|NETWORK|NAS)','[^']+','([^']+)','[^']+',([1-5]),",
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
            raw + b"\\n-- synthetic forged service_owner_id=FAKE\\n",
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
               + "\\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        gen.storyboard_offline(baseline)
        self.assertEqual((json.dumps(baseline, sort_keys=True, indent=2,
                                     ensure_ascii=True) + "\\n").encode("utf-8"), raw)
        self.assertEqual(baseline["seed"], 20261018)
        self.assertEqual(baseline["event_count"], 7)
        self.assertFalse(baseline["publishable_to_core_or_glpi"])


if __name__ == "__main__":
    unittest.main()
