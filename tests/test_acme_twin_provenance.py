"""Deterministic offline contract tests."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from portal.acme_fixture_contract import validate_fixture, load_fixture_bytes
from portal.acme_twin_provenance import build_twin_evidence


class TwinProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / "app/portal/acme-fixtures.json").read_bytes()
        self.fixture = json.loads(self.raw)
        self.view = build_twin_evidence(self.raw)

    def mutate(self, fn):
        fn(self.fixture)
        return json.dumps(self.fixture, ensure_ascii=False).encode()

    def test_exact_fixture_matches_existing_report(self):
        report = validate_fixture(load_fixture_bytes(self.raw))
        impact = self.view["impact"]
        self.assertEqual(impact["impact_path"], report["impact_path"])
        self.assertEqual(impact["affected_ci_ids"], report["affected_ci_ids"])
        self.assertEqual(self.view["incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(self.view["impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(len(self.view["nodes"]), 6)
        self.assertEqual(len(self.view["edges"]), 7)
        self.assertEqual(impact["reachable_ci_count_including_root"], 5)
        self.assertEqual(impact["downstream_ci_count"], 4)

    def test_both_paths_retained_and_primary_edges_reversed(self):
        edges = {(e["source_id"], e["target_id"]) for e in self.view["edges"]}
        for path in (["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"],
                     ["SAN-FABRIC-A", "VOL-PAY-01", "VM-PAY-01", "APP-PAY-01"]):
            self.assertTrue(all((b, a) in edges for a, b in zip(path, path[1:])))
        impact = self.view["impact"]
        path = impact["impact_path"]
        self.assertEqual(path, ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])
        self.assertEqual([(e["source_id"], e["target_id"]) for e in impact["path_edges"]],
                         [(b, a) for a, b in zip(path, path[1:])])

    def test_each_provenance_points_to_exact_fixture_entry(self):
        digest = hashlib.sha256(self.raw).hexdigest()
        for item in self.view["nodes"] + self.view["edges"]:
            p = item["provenance"]
            self.assertEqual(p["source"], "LOCAL_SYNTHETIC_FIXTURE")
            self.assertEqual(p["namespace"], "ACME-DEMO")
            self.assertEqual(p["source_sha256"], digest)
            self.assertIsNone(p["source_sha"])
            self.assertIsNone(p["observed_at"])
            self.assertEqual(p["freshness"], "UNKNOWN")
            self.assertEqual(p["scope"], "STORY_OFFLINE")
            artifact, pointer = p["source_ref"].split("#", 1)
            self.assertEqual(artifact, "app/portal/acme-fixtures.json")
            segments = pointer.strip("/").split("/")
            ci = self.fixture["ci"][int(segments[1])]
            if "node_id" in item:
                self.assertEqual(ci["id"], item["node_id"])
            else:
                self.assertEqual(ci["id"], item["source_id"])
                self.assertEqual(ci["depends_on"][int(segments[3])], item["target_id"])

    def test_redundancy_never_implies_health_or_operational_impact(self):
        impact = self.view["impact"]
        self.assertEqual(impact["alternative_dependency_ids"], ["SAN-FABRIC-B"])
        self.assertNotIn("SAN-FABRIC-B", impact["affected_ci_ids"])
        self.assertEqual(impact["alternative_dependency_health"], "UNKNOWN")
        self.assertEqual(impact["dependency_failure_semantics"], "UNKNOWN")
        self.assertEqual(impact["operational_impact"], "UNKNOWN")
        self.assertFalse(impact["causality_confirmed"])
        self.assertTrue(all(n["state"] == "UNKNOWN" for n in self.view["nodes"]))

    def test_identity_fence_and_same_fixture_run_label(self):
        digest = hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(self.view["run_id"], "SIM-ACME-" + digest[:16].upper())
        for key in ("tenant_id", "attempt_id", "core_run_id", "resource_id", "service_id"):
            self.assertIsNone(self.view[key])
        self.assertEqual(self.view["binding_status"], "UNBOUND")
        for node in self.view["nodes"]:
            self.assertIsNone(node["resource_id"])
            self.assertIsNone(node["service_id"])
        for key in ("runtime_attested", "production_qualified", "live_remediation_authorized"):
            self.assertIs(self.view[key], False)

    def test_deterministic_and_content_bound(self):
        self.assertEqual(self.view, build_twin_evidence(self.raw))
        updated = build_twin_evidence(self.raw + b"\n")
        self.assertNotEqual(self.view["source_sha256"], updated["source_sha256"])
        self.assertNotEqual(self.view["run_id"], updated["run_id"])
        self.assertEqual(self.view["impact"]["impact_path"], updated["impact"]["impact_path"])

    def test_disconnected_payments_rejected(self):
        raw = self.mutate(lambda f: f["ci"][0].update(depends_on=["SAN-FABRIC-B"]))
        with self.assertRaisesRegex(ValueError, "no transitive dependency path"):
            build_twin_evidence(raw)

    def test_unknown_dependency_rejected(self):
        raw = self.mutate(lambda f: f["ci"][1]["depends_on"].append("UNKNOWN-CI"))
        with self.assertRaisesRegex(ValueError, "unknown CI dependency"):
            build_twin_evidence(raw)

    def test_cycle_rejected(self):
        raw = self.mutate(lambda f: f["ci"][4]["depends_on"].append("APP-PAY-01"))
        with self.assertRaisesRegex(ValueError, "cycle"):
            build_twin_evidence(raw)

    def test_fake_runtime_provenance_rejected(self):
        raw = self.mutate(lambda f: f["ci"][0].update(observed_at="2026-11-18T09:00:00Z"))
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            build_twin_evidence(raw)

    def test_cross_namespace_rejected(self):
        raw = self.mutate(lambda f: f.update(organization="ACME-TEST"))
        with self.assertRaisesRegex(ValueError, "organization"):
            build_twin_evidence(raw)

    def test_live_action_rejected(self):
        raw = self.mutate(lambda f: f["incidents"][0].update(live_remediation=True))
        with self.assertRaisesRegex(ValueError, "deny live remediation"):
            build_twin_evidence(raw)

    def test_duplicate_dependency_rejected(self):
        raw = self.mutate(lambda f: f["ci"][0]["depends_on"].append("VM-PAY-01"))
        with self.assertRaisesRegex(ValueError, "duplicate references"):
            build_twin_evidence(raw)

    def test_no_io_or_clock_required(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("builtins.open", side_effect=AssertionError("file I/O forbidden")), \
             patch("time.time", side_effect=AssertionError("clock forbidden")):
            self.assertEqual(self.view, build_twin_evidence(self.raw))


if __name__ == "__main__":
    unittest.main()
