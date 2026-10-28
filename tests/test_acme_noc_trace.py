"""ACME NOC synthetic trace: canonical IDs, missing sources, auth and regressions."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-noc-test-only"}):
    from portal import main
from fastapi.testclient import TestClient
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_noc_trace import build_trace

TOKEN = "synthetic-noc-viewer"
PATH = "/api/noc/acme-trace"


class AcmeNocTraceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def get(self):
        return self.client.get(PATH, headers={"Authorization": "Bearer " + TOKEN})

    def test_auth_before_any_fixture_read(self):
        for headers in ({}, {"Authorization": "Basic " + TOKEN},
                        {"Authorization": "Bearer wrong"}):
            with self.subTest(headers=headers), patch(
                "portal.acme_noc_trace._load_or_503",
                side_effect=AssertionError("fixture accessed before auth")) as read:
                response = self.client.get(PATH, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
                read.assert_not_called()
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            self.assertEqual(self.get().status_code, 503)

    def test_deterministic_canonical_ids_clock_unknown_metrics_and_rag(self):
        a, b = self.get(), self.get()
        self.assertEqual(a.status_code, 200)
        self.assertEqual(a.json(), b.json())
        data = a.json()
        self.assertEqual(data["schema"], "aiops.acme-noc-trace.v1")
        self.assertEqual(data["scenario_schema"], "aiops.acme-scenario.v1")
        self.assertEqual(data["provenance"], "SIMULATED_TARGET")
        self.assertEqual(data["incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(data["impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(data["impact_path"],
                         ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])
        self.assertEqual([e["event_id"] for e in data["events"]],
                         [f"SIM-EVT-ACME-{i:03d}" for i in range(1, 10)])
        self.assertEqual([e["virtual_offset_seconds"] for e in data["events"]],
                         list(range(0, 540, 60)))
        self.assertEqual(data["events"][-1]["virtual_time_utc"], "2026-10-25T09:08:00Z")
        self.assertTrue(all(e["status"] == "MISSING" and e["event_timestamp_utc"] is None
                            for e in data["events"]))
        self.assertEqual({m["ci_id"] for m in data["metrics"]},
                         {"SAN-FABRIC-A", "APP-PAY-01"})
        self.assertTrue(all(m["value"] is None and m["state"] == "NOT_OBSERVED"
                            and m["source"] == "GRAFANA_NOT_QUERIED" for m in data["metrics"]))
        self.assertEqual(data["diagnostic"]["state"], "SYNTHETIC_HYPOTHESIS_ONLY")
        self.assertEqual([c["doc_id"] for c in data["diagnostic"]["citations"]],
                         ["SYN-VMW-APD-001"])
        self.assertEqual(data["diagnostic"]["citations"][0]["asset"], "esx-acme-01")
        self.assertFalse(data["diagnostic"]["llm_inference_performed"])
        for field in ("tenant_acl_qualified", "runtime_attested", "production_qualified",
                      "live_remediation_authorized", "backend_writes"):
            self.assertIs(data[field], False)
        self.assertEqual(data["grafana_observation"], "NOT_TESTED")
        self.assertEqual(a.headers["cache-control"], "no-store")

    def test_tampered_clock_runtime_and_tenant_claim_fail_closed(self):
        valid = build_acme_impact_read_model()
        for key, value in (
            ("simulation_checkpoint_timestamp_utc", "2026-10-28T00:00:00Z"),
            ("simulation_timestamp_provenance", "OBSERVED"),
            ("runtime_attested", True),
            ("impact_path", ["SAN-FABRIC-A", "APP-PAY-01"]),
            ("ownerTenantId", None),
        ):
            with self.subTest(key=key):
                modified = copy.deepcopy(valid)
                modified[key] = value
                with patch("portal.acme_noc_trace._load_or_503", return_value=modified):
                    response = self.get()
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["state"], "UNKNOWN")
                self.assertNotIn("ACME-DEMO-SAN-001", response.text)

    def test_missing_rag_source_is_503_without_internal_details(self):
        with patch("portal.acme_noc_trace.build_demo_rag",
                   side_effect=OSError("private catalog path")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("private", response.text)

    def test_absent_exact_citation_does_not_invent_diagnosis(self):
        from portal.noc_demo_rag import build_demo_rag
        no_match = build_demo_rag("unknown-asset")
        with patch("portal.acme_noc_trace.build_demo_rag",
                   return_value={**no_match, "asset": "esx-acme-01"}):
            data = build_trace(build_acme_impact_read_model())
        self.assertEqual(data["diagnostic"]["state"], "UNKNOWN_NO_EXACT_SOURCE")
        self.assertEqual(data["diagnostic"]["citations"], [])

    def test_visible_portal_and_no_implicit_grafana_io(self):
        self.assertIn("Lire trace ACME NOC", self.client.get("/").text)
        with patch("portal.noc_grafana_health.read_grafana_health",
                   side_effect=AssertionError("Grafana not required")):
            self.assertEqual(self.get().status_code, 200)


if __name__ == "__main__":
    unittest.main()
