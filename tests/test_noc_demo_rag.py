"""Synthetic fixture unit/HTTP contract tests; not real NOC/RAG integration."""
import copy
import os
import pathlib
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import noc_demo_rag

TOKEN = "synthetic-operator-read-token"


class NocDemoRagTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(noc_demo_rag.router)
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()
        self.addCleanup(self.env.stop)

    def get(self, asset="brocade-fc01", token=TOKEN):
        return self.client.get("/api/noc/demo-rag", params={"asset": asset},
                               headers={"Authorization": "Bearer " + token})

    def test_exact_asset_match_cites_only_synthetic_source(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "SYNTHETIC_REFERENCE_ONLY")
        self.assertEqual([x["doc_id"] for x in body["citations"]], ["SYN-FOS-FC-CRC-001"])
        self.assertEqual(body["citations"][0]["asset"], "brocade-fc01")
        self.assertEqual(len(body["catalog_sha256"]), 64)
        self.assertFalse(body["llm_inference_performed"])
        self.assertFalse(body["tenant_acl_qualified"])
        self.assertFalse(body["source_runtime_observed"])
        self.assertFalse(body["live_remediation_authorized"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_absent_asset_returns_unknown_not_invented_evidence(self):
        body = self.get("unknown-asset").json()
        self.assertEqual(body["state"], "UNKNOWN")
        self.assertEqual(body["citations"], [])
        self.assertEqual(body["grafana_observation"], "NOT_TESTED")

    def test_invalid_asset_fails_closed(self):
        for asset in ("../passwd", "host%2Fetc", "", "a" * 120):
            with self.subTest(asset=asset):
                response = self.get(asset)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_missing_auth_prevents_catalog_access(self):
        with patch.object(noc_demo_rag, "load_catalog", side_effect=AssertionError("no fixture read")):
            response = self.get(token="wrong")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("fixture", response.text)

    def test_missing_auth_configuration_is_unavailable(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            response = self.get()
        self.assertEqual(response.status_code, 503)

    def test_catalog_absence_returns_503_without_leaking_paths(self):
        with patch.object(noc_demo_rag, "FIXTURE_PATH", pathlib.Path("/nonexistent/fixture.json")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("nonexistent", response.text)

    def test_duplicate_json_keys_are_rejected(self):
        with patch.object(noc_demo_rag, "FIXTURE_PATH", Mock(read_bytes=Mock(return_value=b'{"schema":1,"schema":2}'))):
            response = self.get()
        self.assertEqual(response.status_code, 503)

    def test_rejects_live_claim_and_unlabelled_sample(self):
        rows, _ = noc_demo_rag.load_catalog()
        for change in ({"source_type": "LIVE"}, {"sample": "Observed real CRC error"},
                       {"doc_id": "../bad"}, {"runbook": ["a"] * 21}):
            altered = copy.deepcopy(rows)
            altered[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                noc_demo_rag.validate_catalog({"schema": noc_demo_rag.CATALOG_SCHEMA,
                    "provenance": "SYNTHETIC_SIMULATION_ONLY", "scenarios": altered})

    def test_rejects_duplicate_document_or_event(self):
        rows, _ = noc_demo_rag.load_catalog()
        for key in ("doc_id", "event_key"):
            altered = copy.deepcopy(rows)
            altered[1][key] = altered[0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                noc_demo_rag.validate_catalog({"schema": noc_demo_rag.CATALOG_SCHEMA,
                    "provenance": "SYNTHETIC_SIMULATION_ONLY", "scenarios": altered})

    def test_rejects_malformed_kind_type(self):
        rows, _ = noc_demo_rag.load_catalog()
        altered = copy.deepcopy(rows)
        altered[0]["kind"] = ["RUNBOOK"]
        with self.assertRaises(ValueError):
            noc_demo_rag.validate_catalog({"schema": noc_demo_rag.CATALOG_SCHEMA,
                "provenance": "SYNTHETIC_SIMULATION_ONLY", "scenarios": altered})

    def test_portal_route_and_visible_demo_control(self):
        from portal import main as portal_main
        self.assertIn("/api/noc/demo-rag", [route.path for route in portal_main.app.routes])
        snapshot = {"dashboard": {}, "runs": {"items": []}, "twin": {}, "states": {}}
        with patch.object(portal_main, "read_portal_snapshot", return_value=snapshot), \
             patch.object(portal_main, "build_navigation", return_value={}), \
             patch.object(portal_main, "render_navigation_html", return_value=""):
            page = portal_main.home()
        self.assertIn("Lire fiches RAG DEMO", page)
        self.assertIn("synthétiques", page)
        self.assertIn("encodeURIComponent(asset)", page)
        self.assertIn("el.value=''", page)
        self.assertIn("out.textContent", page)

    def test_rejects_invalid_digest_even_if_rows_valid(self):
        rows, _ = noc_demo_rag.load_catalog()
        with self.assertRaises(ValueError):
            noc_demo_rag.build_demo_rag("brocade-fc01", catalog=(rows, "bad-digest"))


if __name__ == "__main__":
    unittest.main()
