"""Contract/API tests: local synthetic fixtures only; no runtime integration claim."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-contract-test-only"}):
    from portal import main
from fastapi.testclient import TestClient
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_scenario_contract import build_acme_scenario_contract, CUES
from portal.acme_fixture_contract import load_fixture, validate_fixture

TOKEN = "synthetic-contract-viewer"
PATH = "/api/demo/acme-scenario"


class AcmeScenarioContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def get(self, token=TOKEN):
        return self.client.get(PATH, headers={"Authorization": "Bearer " + token})

    def test_v1_fixture_unmodified_and_canonical_ids(self):
        fixture = load_fixture(Path(__file__).resolve().parents[1] / "app/portal/acme-fixtures.json")
        report = validate_fixture(fixture)
        self.assertEqual(fixture["schema"], "aiops.acme.demo.v1")
        self.assertEqual(report["ci_count"], 6)
        self.assertEqual(report["incident_count"], 2)
        self.assertEqual(report["impact_path"],
                         ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])

    def test_authenticated_read_is_deterministic_and_has_no_runtime_proof(self):
        a, b = self.get(), self.get()
        self.assertEqual(a.status_code, 200)
        self.assertEqual(a.json(), b.json())
        self.assertEqual(a.headers["cache-control"], "no-store")
        data = a.json()
        self.assertEqual(data["schema"], "aiops.acme-scenario.v1")
        self.assertEqual(data["mode"], "DEMO")
        self.assertEqual(data["state"], "SIMULATED_UNVERIFIED")
        self.assertEqual(data["provenance"], "SIMULATED_TARGET")
        self.assertEqual(data["source_sha256"], build_acme_impact_read_model()["source_sha256"])
        self.assertEqual([e["cue"] for e in data["events"]], list(CUES))
        self.assertEqual([e["id"] for e in data["events"]],
                         [f"SIM-EVT-ACME-{n:03d}" for n in range(1, 10)])
        self.assertEqual(data["event_count"], 9)
        self.assertTrue(all(e["status"] == "MISSING" and e["event_timestamp_utc"] is None
                            and e["incident_id"] == "ACME-DEMO-SAN-001"
                            for e in data["events"]))
        self.assertIsNone(data["scenario"]["ticket_id"])
        self.assertIsNone(data["scenario"]["event_timestamp_utc"])
        self.assertTrue(data["scenario"]["run_id"].startswith("SIM-ACME-"))
        for key in ("runtime_attested", "production_qualified",
                    "live_remediation_authorized", "backend_writes"):
            self.assertIs(data[key], False)

    def test_explore_and_story_use_same_event_contract(self):
        canonical = self.get().json()
        for mode in ("explore", "story"):
            response = self.client.post("/api/demo/explore-story/control",
                json={"action": "start", "cursor": 0, "mode": mode},
                headers={"Authorization": "Bearer " + TOKEN})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["source_sha256"], canonical["source_sha256"])
            self.assertEqual(data["scenario"]["run_id"], canonical["scenario"]["run_id"])
            self.assertEqual(data["scenario"]["incident_id"], canonical["scenario"]["incident_id"])
            self.assertEqual(data["scenario"]["impact_path"], canonical["scenario"]["impact_path"])
            self.assertEqual(data["timeline"],
                [{key: e[key] for key in ("cue", "service", "view", "status")}
                 for e in canonical["events"]])

    def test_auth_fails_before_fixture_read(self):
        for headers in ({}, {"Authorization": "Basic " + TOKEN},
                        {"Authorization": "Bearer wrong"}):
            with self.subTest(headers=headers), patch(
                "portal.acme_explore_story._load_or_503",
                side_effect=AssertionError("fixture accessed without auth")) as read:
                response = self.client.get(PATH, headers=headers)
                self.assertEqual(response.status_code, 401)
                read.assert_not_called()
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            self.assertEqual(self.get().status_code, 503)

    def test_tampering_with_runtime_flags_and_ids_fails_closed(self):
        valid = build_acme_impact_read_model()
        for key, value in (("runtime_attested", True), ("production_qualified", True),
                           ("live_remediation_authorized", True),
                           ("ticket_id", 123), ("event_timestamp_utc", "2026-10-28T00:00:00Z"),
                           ("run_id", "RUN-REAL"), ("source_sha256", "invalid"),
                           ("impact_path", ["SAN-FABRIC-A", "APP-PAY-01"])):
            with self.subTest(key=key):
                model = copy.deepcopy(valid)
                model[key] = value
                with self.assertRaises(ValueError):
                    build_acme_scenario_contract(model)
        for mutation in ({"status": "SUCCESS"}, {"runtime_authenticated": True},
                         {"screenshot_sha256": "f" * 64}, {"cue": "execute"}):
            with self.subTest(mutation=mutation):
                model = copy.deepcopy(valid)
                model["checkpoint_evidence"][0].update(mutation)
                with self.assertRaises(ValueError):
                    build_acme_scenario_contract(model)

    def test_invalid_projection_is_unknown_and_does_not_leak(self):
        with patch("portal.acme_explore_story._load_or_503",
                   side_effect=main.HTTPException(status_code=503, detail="private")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("private", response.text)


if __name__ == "__main__":
    unittest.main()
