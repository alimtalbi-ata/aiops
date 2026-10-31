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
from portal.acme_impact_read_model import (
    FIXTURE_PATH, build_acme_impact_read_model, router,
)
from portal.acme_explore_story import router as explore_story_router

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

    def test_itil_story_projects_explicit_synthetic_roles_handoffs_and_evidence_gates(self):
        model = build_acme_impact_read_model()
        steps = model["checkpoint_evidence"]
        self.assertEqual(len(steps), 14)
        self.assertEqual(steps[0]["itil_practice"], "monitoring_event_management")
        self.assertEqual(steps[0]["owner_role"], "noc_l1")
        self.assertEqual(steps[2]["owner_role"], "service_desk_n1")
        self.assertEqual(steps[4]["owner_role"], "incident_commander")
        self.assertEqual(steps[9]["owner_role"], "authorized_approver")
        self.assertEqual(steps[-1]["itil_practice"], "continual_improvement")
        self.assertTrue(all(
            step["status"] == "MISSING"
            and step["runtime_authenticated"] is False
            and step["source"] == "SYNTHETIC_ITIL_CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE"
            and step["evidence_required"]
            for step in steps
        ))

        app = FastAPI()
        app.include_router(explore_story_router)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "unit-test-only"}):
            response = TestClient(app).post(
                "/api/demo/explore-story/control",
                headers={"Authorization": "Bearer unit-test-only"},
                json={"action": "start", "cursor": 0, "mode": "story"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["timeline"]), 14)
        self.assertEqual(payload["timeline"][9]["owner_role"], "authorized_approver")
        self.assertTrue(all(item["status"] == "MISSING" for item in payload["timeline"]))
        self.assertFalse(payload["runtime_attested"])
        self.assertFalse(payload["production_qualified"])
        self.assertFalse(payload["live_remediation_authorized"])

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
        page = client.get("/demo/acme-impact")
        self.assertEqual(page.status_code, 200)
        self.assertIn("SIMULATION LOCALE UNIQUEMENT", page.text)
        self.assertIn("SAN-FABRIC-A", page.text)
        self.assertIn("APP-PAY-01", page.text)

    def test_canonical_portal_mounts_acme_routes(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
            from portal.main import app as canonical_app
        paths = {route.path for route in canonical_app.routes}
        self.assertIn("/api/demo/acme-impact", paths)
        self.assertIn("/demo/acme-impact", paths)
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
