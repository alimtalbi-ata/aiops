"""Offline contract tests; these do not qualify any GLPI or runtime integration."""
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.acme_fixture_contract import load_fixture_bytes, validate_fixture
from portal.acme_declared_topology import build_declared_topology
from portal.acme_impact_read_model import (
    FIXTURE_PATH, build_acme_impact_read_model, router,
)

class AcmeImpactTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE_PATH.read_bytes()
        self.fixture = load_fixture_bytes(self.raw)

    def test_stable_san_to_payments_path_and_blast_radius(self):
        report = validate_fixture(self.fixture)
        self.assertEqual(report["impact_path"][0], "SAN-FABRIC-A")
        self.assertEqual(report["impact_path"][-1], "APP-PAY-01")
        self.assertIn("HOST-ESX-01", report["affected_ci_ids"])
        self.assertIn("VM-PAY-01", report["affected_ci_ids"])
        self.assertFalse(report["live_remediation_authorized"])

    def test_deterministic_ids_and_no_glpi_runtime_claim(self):
        first = build_acme_impact_read_model()
        self.assertEqual(first, build_acme_impact_read_model())
        self.assertEqual(first["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(first["incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(first["impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertTrue(first["run_id"].startswith("SIM-ACME-"))
        self.assertTrue(first["simulation_ticket_id"].startswith("SIM-GLPI-"))
        self.assertIsNone(first["ticket_id"])
        self.assertIsNone(first["event_timestamp_utc"])
        self.assertFalse(first["runtime_attested"])
        self.assertFalse(first["production_qualified"])
        self.assertFalse(first["live_remediation_authorized"])
        self.assertTrue(all(not item["runtime_authenticated"] and item["status"] == "MISSING"
                            for item in first["checkpoint_evidence"]))

    def test_full_topology_is_stable_and_does_not_infer_failover(self):
        topology = build_declared_topology(self.fixture)
        self.assertEqual(topology, build_declared_topology(self.fixture))
        self.assertEqual(topology["schema"], "aiops.acme.declared-topology.v1")
        self.assertEqual(len(topology["nodes"]), 6)
        self.assertEqual(len(topology["edges"]), 7)
        self.assertEqual(topology["edges"], sorted(topology["edges"],
            key=lambda edge: (edge["from"], edge["to"])))
        self.assertEqual(topology["alternate_declared_path"],
                         ["SAN-FABRIC-B", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])
        self.assertEqual(topology["alternate_path_status"], "DECLARED_NOT_VERIFIED")
        self.assertFalse(topology["failover_verified"])
        self.assertFalse(topology["cmdb_verified"])
        self.assertFalse(topology["live_discovery"])
        self.assertFalse(topology["live_remediation_authorized"])
        self.assertEqual(topology["runtime_health"], "UNKNOWN")
        self.assertIsNone(topology["glpi_ticket_id"])
        self.assertIsNone(topology["glpi_ticket_url"])
        self.assertIsNone(topology["canonical_run_id"])
        self.assertFalse(next(n for n in topology["nodes"]
                              if n["id"] == "SAN-FABRIC-B")["affected_by_source"])

    def test_topology_independent_of_fixture_order(self):
        changed = copy.deepcopy(self.fixture)
        changed["ci"].reverse()
        for ci in changed["ci"]:
            ci["depends_on"].reverse()
        self.assertEqual(build_declared_topology(changed),
                         build_declared_topology(self.fixture))

    def test_topology_missing_alternate_fails_closed_to_unknown(self):
        changed = copy.deepcopy(self.fixture)
        changed["ci"] = [ci for ci in changed["ci"] if ci["id"] != "SAN-FABRIC-B"]
        for ci in changed["ci"]:
            ci["depends_on"] = [ref for ref in ci["depends_on"] if ref != "SAN-FABRIC-B"]
        changed["ci"].append({"id": "DUMMY-01", "kind": "NetworkDevice",
                              "name": "isolated dummy", "depends_on": []})
        topology = build_declared_topology(changed)
        self.assertIsNone(topology["alternate_declared_path"])
        self.assertIsNone(topology["alternate_fabric_id"])
        self.assertEqual(topology["alternate_path_status"], "UNKNOWN")
        self.assertFalse(topology["failover_verified"])

    def test_topology_rejects_live_and_unknown_dependencies(self):
        for key, value in (("status", "LIVE"), ("live_remediation", True)):
            changed = copy.deepcopy(self.fixture)
            changed["incidents"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_declared_topology(changed)
        changed = copy.deepcopy(self.fixture)
        changed["ci"][0]["depends_on"] = ["NOT-A-CI"]
        with self.assertRaises(ValueError):
            build_declared_topology(changed)

    def test_rejects_live_or_unsafe_actions(self):
        for key, value in (("status", "open"), ("live_remediation", True),
                           ("allowed_actions", ["execute"])):
            changed = copy.deepcopy(self.fixture)
            changed["incidents"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_fixture(changed)

    def test_rejects_cycles_and_unknown_dependencies(self):
        for refs in (["APP-PAY-01"], ["NONEXISTENT"]):
            changed = copy.deepcopy(self.fixture)
            next(ci for ci in changed["ci"] if ci["id"] == "SAN-FABRIC-A")["depends_on"] = refs
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                validate_fixture(changed)

    def test_duplicate_json_keys_fail_closed(self):
        with self.assertRaises(ValueError):
            load_fixture_bytes(b'{"schema":"a","schema":"b"}')

    def test_api_and_page_explicitly_synthetic(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        response = client.get("/api/demo/acme-impact")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provenance"], "SIMULATED_TARGET")
        self.assertEqual(response.headers["cache-control"], "no-store")
        topology = client.get("/api/demo/acme-topology")
        self.assertEqual(topology.status_code, 200)
        self.assertEqual(topology.headers["cache-control"], "no-store")
        self.assertEqual(topology.json(), response.json()["topology"])
        self.assertEqual(topology.json()["source_sha256"], response.json()["source_sha256"])
        self.assertEqual(topology.json()["simulation_run_id"], response.json()["run_id"])
        self.assertIsNone(topology.json()["glpi_ticket_url"])
        page = client.get("/demo/acme-impact")
        self.assertEqual(page.status_code, 200)
        self.assertIn("SIMULATION LOCALE UNIQUEMENT", page.text)
        self.assertIn("SAN-FABRIC-A", page.text)
        self.assertIn("APP-PAY-01", page.text)
        self.assertIn("Topologie déclarative", page.text)
        self.assertIn("Failover vérifié", page.text)
        self.assertIn("SAN-FABRIC-B", page.text)

    def test_canonical_portal_mounts_acme_routes(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
            from portal.main import app as canonical_app
        paths = {route.path for route in canonical_app.routes}
        self.assertIn("/api/demo/acme-impact", paths)
        self.assertIn("/demo/acme-impact", paths)
        self.assertIn("/api/demo/acme-topology", paths)
        page = TestClient(canonical_app).get("/demo/acme-impact")
        self.assertEqual(page.status_code, 200)
        self.assertIn("SIMULATION LOCALE UNIQUEMENT", page.text)

    def test_invalid_fixture_returns_503_not_healthy_demo(self):
        app = FastAPI()
        app.include_router(router)
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "fixture.json"
            bad.write_text('{"schema":"aiops.acme.demo.v1"}')
            with patch("portal.acme_impact_read_model.FIXTURE_PATH", bad):
                response = TestClient(app).get("/api/demo/acme-impact")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("SIM-ACME-", response.text)
                topology = TestClient(app).get("/api/demo/acme-topology")
                self.assertEqual(topology.status_code, 503)
                self.assertNotIn("SAN-FABRIC-B", topology.text)

    def test_topology_html_escapes_untrusted_fixture_names(self):
        changed = copy.deepcopy(self.fixture)
        changed["ci"][0]["name"] = "<script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as d:
            fixture = Path(d) / "fixture.json"
            fixture.write_text(json.dumps(changed), encoding="utf-8")
            with patch("portal.acme_impact_read_model.FIXTURE_PATH", fixture):
                app = FastAPI()
                app.include_router(router)
                page = TestClient(app).get("/demo/acme-impact")
                self.assertEqual(page.status_code, 200)
                self.assertNotIn("<script>alert(1)</script>", page.text)
                self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page.text)

    def test_symlink_fixture_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d) / "fixture.json"
            original.write_bytes(self.raw)
            symlink = Path(d) / "link.json"
            symlink.symlink_to(original)
            with patch("portal.acme_impact_read_model.FIXTURE_PATH", symlink):
                with self.assertRaises(ValueError):
                    build_acme_impact_read_model()

if __name__ == "__main__":
    unittest.main()
