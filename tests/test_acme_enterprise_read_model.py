"""Offline P0 enterprise fixture contracts, not a runtime/GLPI integration test."""
import copy
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.acme_fixture_contract import (
    expand_enterprise_fixture, load_fixture_bytes, validate_fixture,
)
from portal.acme_enterprise_read_model import (
    build_acme_enterprise_read_model, router,
)
from portal.acme_impact_read_model import FIXTURE_PATH


class EnterpriseFixtureTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE_PATH.read_bytes()
        self.seed = load_fixture_bytes(self.raw)

    def test_v1_schema_unchanged_and_expansion_has_exact_counts(self):
        before = copy.deepcopy(self.seed)
        expanded = expand_enterprise_fixture(self.seed)
        self.assertEqual(self.seed, before)
        self.assertEqual(self.seed["schema"], "aiops.acme.demo.v1")
        self.assertEqual(expanded["schema"], "aiops.acme.demo.v1")
        self.assertEqual(len(expanded["ci"]), 60)
        self.assertEqual(len(expanded["incidents"]), 6)
        report = validate_fixture(expanded)
        self.assertEqual(report["impact_path"][0], "SAN-FABRIC-A")
        self.assertEqual(report["impact_path"][-1], "APP-PAY-01")
        self.assertIn("HOST-ESX-01", report["impact_path"])
        self.assertIn("VM-PAY-01", report["impact_path"])

    def test_deterministic_sites_events_tickets_and_source_digest(self):
        a = build_acme_enterprise_read_model()
        self.assertEqual(a, build_acme_enterprise_read_model())
        self.assertEqual(a["ci_count"], 60)
        self.assertEqual(a["incident_count"], 6)
        self.assertEqual(len(a["sites"]), 4)
        self.assertEqual(len(a["applications"]), 5)
        self.assertEqual(len(a["events"]), 6)
        self.assertEqual(len(a["tickets"]), 6)
        self.assertEqual(a["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        ids = {item["id"] for item in a["ci"]}
        self.assertEqual(len(ids), 60)
        self.assertTrue(all(set(ci["depends_on"]) <= ids for ci in a["ci"]))
        self.assertTrue(all(ci["site_id"] in {site["id"] for site in a["sites"]}
                            for ci in a["ci"]))
        self.assertTrue(all(t["glpi_ticket_id"] is None and t["core_run_id"] is None
                            and t["status"] == "SIMULATED_NOT_IN_GLPI"
                            for t in a["tickets"]))
        self.assertTrue(all(t["incident_id"] == e["incident_id"]
                            and t["event_id"] == e["id"]
                            for t, e in zip(a["tickets"], a["events"])))
        self.assertEqual(a["mode"], "DEMO")
        self.assertEqual(a["provenance"], "SIMULATED_TARGET")
        self.assertFalse(a["runtime_attested"])
        self.assertFalse(a["live_remediation_authorized"])
        self.assertFalse(a["backend_writes"])

    def test_fail_closed_on_unsafe_or_noncanonical_v1_seed(self):
        for mutation in ("live", "action", "extra", "cycle"):
            changed = copy.deepcopy(self.seed)
            if mutation == "live":
                changed["incidents"][0]["live_remediation"] = True
            elif mutation == "action":
                changed["incidents"][0]["allowed_actions"] = ["execute"]
            elif mutation == "extra":
                changed["ci"].append(copy.deepcopy(changed["ci"][0]))
                changed["ci"][-1]["id"] = "UNEXPECTED-CI"
            else:
                next(ci for ci in changed["ci"] if ci["id"] == "SAN-FABRIC-A")["depends_on"] = ["APP-PAY-01"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                expand_enterprise_fixture(changed)

    def test_explore_story_are_same_read_only_canonical_projection(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        explore = client.get("/api/demo/acme-enterprise/explore")
        story = client.get("/api/demo/acme-enterprise/story")
        self.assertEqual(explore.status_code, 200)
        self.assertEqual(story.status_code, 200)
        self.assertEqual(explore.json(), story.json())
        self.assertEqual(explore.headers["cache-control"], "no-store")
        self.assertEqual(explore.headers["x-frame-options"], "DENY")
        self.assertIsNone(explore.json()["tickets"][0]["glpi_ticket_id"])

    def test_canonical_portal_mounts_both_endpoints(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-only"}):
            from portal.main import app
        paths = {route.path for route in app.routes}
        self.assertIn("/api/demo/acme-enterprise/explore", paths)
        self.assertIn("/api/demo/acme-enterprise/story", paths)

    def test_invalid_or_symlink_fixture_returns_503(self):
        app = FastAPI()
        app.include_router(router)
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.json"
            bad.write_text('{"schema":"aiops.acme.demo.v1"}')
            with patch("portal.acme_enterprise_read_model.FIXTURE_PATH", bad):
                response = TestClient(app).get("/api/demo/acme-enterprise/explore")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("SIM-GLPI", response.text)
            link = Path(folder) / "link.json"
            link.symlink_to(FIXTURE_PATH)
            with patch("portal.acme_enterprise_read_model.FIXTURE_PATH", link):
                response = TestClient(app).get("/api/demo/acme-enterprise/story")
                self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
