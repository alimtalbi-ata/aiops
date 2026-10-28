"""Unit/HTTP regression tests with synthetic inputs, NOT Checkmk/Core integration."""
import copy
import hashlib
import hmac
import json
import os
import pathlib
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import noc_demo_context, noc_demo_rag, noc_runtime

TOKEN = "synthetic-noc-operator-token"
KEY = b"synthetic-32-byte-test-hmac-key-0000000"


def noc():
    return {
        "schema": noc_runtime.OUTPUT_SCHEMA,
        "source_payload_authenticated": True,
        "source_authentication": "HMAC_SHA256_VERIFIED",
        "runtime_authenticated": False,
        "live_remediation_authorized": False,
        "tenant_acl_qualified": False,
        "run_id": "RUN-DEMO-001", "incident_id": "INC-DEMO-001",
        "source_origin": "https://noc.example.test",
        "source_payload_sha256": "a" * 64,
        "asset": "brocade-fc01", "event_key": "DEMO_FC_PORT_CRC_SPIKE",
    }


def run():
    return {"run_id": "RUN-DEMO-001", "incident_id": "INC-DEMO-001",
            "status": "BLOCKED", "mode": "DEMO"}


class NocDemoContextTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(noc_demo_context.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()
        self.addCleanup(self.env.stop)

    def get(self, token=TOKEN):
        return self.client.get("/api/noc/demo-context",
                               headers={"Authorization": "Bearer " + token})

    def test_exact_signed_demo_identity_and_event_cite_synthetic_only(self):
        result = noc_demo_context.build_demo_context(noc(), run())
        self.assertEqual(result["state"], "SYNTHETIC_CONTEXT_ONLY")
        self.assertEqual(result["reason"], "SIGNED_IDENTITIES_AND_SYNTHETIC_EVENT_KEY_MATCH")
        self.assertEqual([c["doc_id"] for c in result["citations"]], ["SYN-FOS-FC-CRC-001"])
        self.assertEqual(result["canonical_run_id"], "RUN-DEMO-001")
        self.assertEqual(len(result["catalog_sha256"]), 64)
        self.assertEqual(result["data_classification"], "SYNTHETIC_SIMULATION_ONLY")
        for flag in ("tenant_acl_qualified", "source_runtime_observed",
                     "llm_inference_performed", "runtime_authenticated",
                     "production_qualified", "live_remediation_authorized"):
            self.assertIs(result[flag], False)

    def test_run_or_incident_mismatch_never_reads_catalog(self):
        for field in ("run_id", "incident_id"):
            changed = run()
            changed[field] = "DIFFERENT"
            with self.subTest(field=field), patch.object(
                noc_demo_rag, "build_demo_rag", side_effect=AssertionError("catalog must not load")
            ):
                result = noc_demo_context.build_demo_context(noc(), changed)
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertEqual(result["citations"], [])
            self.assertNotIn("canonical_run_id", result)

    def test_live_replay_and_story_never_load_catalog(self):
        for mode in ("LIVE", "REPLAY", "STORY"):
            changed = run()
            changed["mode"] = mode
            with self.subTest(mode=mode), patch.object(
                noc_demo_rag, "build_demo_rag", side_effect=AssertionError("catalog must not load")
            ):
                result = noc_demo_context.build_demo_context(noc(), changed)
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertEqual(result["citations"], [])

    def test_missing_asset_or_event_is_unknown_without_catalog_read(self):
        for field in ("asset", "event_key"):
            changed = noc()
            changed[field] = None
            with self.subTest(field=field), patch.object(
                noc_demo_rag, "build_demo_rag", side_effect=AssertionError("catalog must not load")
            ):
                result = noc_demo_context.build_demo_context(changed, run())
            self.assertEqual(result["reason"], "SIGNED_ASSET_OR_EVENT_ABSENT")

    def test_unmatched_event_or_asset_has_no_citation(self):
        for field, value in (("event_key", "DEMO_UNRELATED"), ("asset", "unknown-host")):
            changed = noc()
            changed[field] = value
            result = noc_demo_context.build_demo_context(changed, run())
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertEqual(result["citations"], [])

    def test_tenant_scopes_are_denied_not_guessed(self):
        for field in ("tenant_id", "tenant", "organization_id", "org_id"):
            changed = run()
            changed[field] = "TENANT-B"
            with self.subTest(field=field), self.assertRaises(ValueError):
                noc_demo_context.build_demo_context(noc(), changed)
        changed = noc()
        changed["tenant_acl_qualified"] = True
        with self.assertRaises(ValueError):
            noc_demo_context.build_demo_context(changed, run())

    def test_unverified_noc_signature_and_claims_rejected(self):
        for field, value in (("source_payload_authenticated", False),
                             ("source_authentication", "NONE"),
                             ("runtime_authenticated", True),
                             ("live_remediation_authorized", True)):
            changed = noc()
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                noc_demo_context.build_demo_context(changed, run())

    def test_corrupt_catalog_fails_closed(self):
        with patch.object(noc_demo_rag, "FIXTURE_PATH", pathlib.Path("/nonexistent/demo-fixture")):
            with self.assertRaises(OSError):
                noc_demo_context.build_demo_context(noc(), run())

    def test_signed_payload_validates_asset_event_and_refuses_tenant_metadata(self):
        base = {
            "schema": noc_runtime.SCHEMA, "provenance": "RUNTIME_READMODEL",
            "run_id": "RUN-DEMO-001", "incident_id": "INC-DEMO-001",
            "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "steps": [{"name": "detect", "state": "WARN"}],
            "asset": "brocade-fc01", "event_key": "DEMO_FC_PORT_CRC_SPIKE",
        }
        def project(payload):
            raw = json.dumps(payload, separators=(",", ":")).encode()
            return noc_runtime._project_signed_payload(
                raw, digest_header=hashlib.sha256(raw).hexdigest(),
                signature_header=hmac.new(KEY, raw, hashlib.sha256).hexdigest(),
                hmac_key=KEY, source_origin="https://noc.example.test")
        projected = project(base)
        self.assertEqual(projected["asset"], "brocade-fc01")
        self.assertEqual(projected["event_key"], "DEMO_FC_PORT_CRC_SPIKE")
        self.assertFalse(projected["tenant_acl_qualified"])
        for change in ({"asset": "../other"}, {"event_key": []},
                       {"tenant_id": "OTHER"}, {"organization_id": "OTHER"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                project({**base, **change})

    def test_authentication_fails_before_any_upstream_access(self):
        with patch.object(noc_runtime, "read_signed_noc_snapshot",
                          side_effect=AssertionError("no upstream before auth")):
            response = self.get("wrong")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_missing_auth_config_fails_before_upstream(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            noc_runtime, "read_signed_noc_snapshot", side_effect=AssertionError("no upstream")
        ):
            response = self.get()
        self.assertEqual(response.status_code, 503)

    def test_missing_source_returns_503_not_synthetic_fallback(self):
        with patch.object(noc_runtime, "read_signed_noc_snapshot",
                          side_effect=noc_runtime.NocSourceNotConfigured("absent")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "noc_source_not_configured")

    def test_core_unavailable_never_falls_back_to_fixtures(self):
        with patch.object(noc_runtime, "read_signed_noc_snapshot", return_value=noc()), \
             patch.object(noc_demo_context.noc_correlation, "_read_core_run",
                          side_effect=OSError("private core URL")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private core URL", response.text)

    def test_route_reads_signed_noc_then_canonical_run_without_writes(self):
        with patch.object(noc_runtime, "read_signed_noc_snapshot", return_value=noc()) as source, \
             patch.object(noc_demo_context.noc_correlation, "_read_core_run", return_value=run()) as core:
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "SYNTHETIC_CONTEXT_ONLY")
        self.assertEqual(response.headers["cache-control"], "no-store")
        source.assert_called_once_with()
        core.assert_called_once_with("RUN-DEMO-001")

    def test_portal_has_visible_signed_demo_context_control(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": TOKEN}):
            from portal import main as portal_main
        self.assertIn("/api/noc/demo-context", [route.path for route in portal_main.app.routes])
        snapshot = {"dashboard": {}, "runs": {"items": []}, "twin": {}, "states": {}}
        with patch.object(portal_main, "read_portal_snapshot", return_value=snapshot), \
             patch.object(portal_main, "build_navigation", return_value={}), \
             patch.object(portal_main, "render_navigation_html", return_value=""):
            html = portal_main.home()
        self.assertIn("Contexte RAG DEMO lié", html)
        self.assertIn("signedDemoContext()", html)
        self.assertIn("redirect:'error'", html)


if __name__ == "__main__":
    unittest.main()
