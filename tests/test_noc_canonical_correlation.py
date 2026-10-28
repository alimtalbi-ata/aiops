"""Offline contract tests only: no actual Checkmk/Thruk/Core or Grafana in this suite."""
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from portal import noc_correlation  # noqa: E402

TOKEN = "synthetic-portal-token-not-a-secret"


def noc_view():
    return {"schema": "aiops.noc-runtime-envelope.v1",
            "source_payload_authenticated": True,
            "source_authentication": "HMAC_SHA256_VERIFIED",
            "runtime_authenticated": False, "live_remediation_authorized": False,
            "source_origin": "https://noc.example.test",
            "source_payload_sha256": "a" * 64,
            "run_id": "RUN-ACME-001", "incident_id": "INC-ACME-001"}


def core_run(mode="DEMO"):
    return {"run_id": "RUN-ACME-001", "incident_id": "INC-ACME-001",
            "mode": mode, "status": "RUNNING", "private_payload": "never exposed"}


class CorrelationTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(noc_correlation.router)
        self.client = TestClient(app)

    def request(self, authorized=True):
        return self.client.get("/api/noc/correlation", headers={
            "Authorization": "Bearer " + (TOKEN if authorized else "bad-token")})

    def test_exact_demo_join_is_not_runtime_attestation(self):
        result = noc_correlation.correlate(noc_view(), core_run())
        self.assertEqual(result["state"], "MATCHED_UNATTESTED")
        self.assertEqual(result["data_classification"], "SYNTHETIC_CANONICAL_RUN")
        self.assertEqual(result["grafana_observation"], "NOT_TESTED")
        self.assertEqual(result["rag_diagnostic"], "NOT_TESTED")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertNotIn("private_payload", str(result))

    def test_live_mode_is_refused_without_runtime_and_tenant_qualification(self):
        with self.assertRaisesRegex(ValueError, "LIVE correlation"):
            noc_correlation.correlate(noc_view(), core_run("LIVE"))

    def test_tenant_scoped_run_or_noc_claims_fail_closed(self):
        for key in ("tenant_id", "organization_id", "org_id", "workspace_id",
                    "account_id", "owner_tenant_id"):
            for side in ("core", "noc"):
                with self.subTest(field=key, side=side), self.assertRaisesRegex(
                        ValueError, "qualified ACL"):
                    run, noc = core_run(), noc_view()
                    (run if side == "core" else noc)[key] = "TENANT-OTHER"
                    noc_correlation.correlate(noc, run)

    def test_legacy_demo_replay_story_remain_explicitly_synthetic(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                result = noc_correlation.correlate(noc_view(), core_run(mode))
                self.assertEqual(result["state"], "MATCHED_UNATTESTED")
                self.assertEqual(result["canonical_mode"], mode)
                self.assertEqual(result["data_classification"], "SYNTHETIC_CANONICAL_RUN")

    def test_tenant_scoped_core_route_denies_without_disclosing_identity(self):
        run = {**core_run(), "tenant_id": "TENANT-PRIVATE"}
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
                noc_correlation.noc_runtime, "read_signed_noc_snapshot", return_value=noc_view()), patch.object(
                noc_correlation, "_read_core_run", return_value=run):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "canonical_correlation_unavailable_or_unverified")
        self.assertNotIn("TENANT-PRIVATE", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_identity_mismatch_does_not_leak_canonical_ids(self):
        run = core_run()
        run["incident_id"] = "INC-OTHER-TENANT"
        result = noc_correlation.correlate(noc_view(), run)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["canonical_run_id"])
        self.assertIsNone(result["canonical_incident_id"])
        self.assertNotIn("OTHER-TENANT", str(result))

    def test_unverified_noc_cannot_correlate(self):
        for change in ({"source_payload_authenticated": False},
                       {"source_authentication": "NONE"},
                       {"runtime_authenticated": True},
                       {"live_remediation_authorized": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                noc_correlation.correlate({**noc_view(), **change}, core_run())

    def test_invalid_canonical_identity_fails_closed(self):
        for change in ({"run_id": "../escape"}, {"mode": "SIMULATION"},
                       {"incident_id": None}, {"status": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                noc_correlation.correlate(noc_view(), {**core_run(), **change})

    def test_auth_denial_prevents_both_upstream_reads(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
                noc_correlation.noc_runtime, "read_signed_noc_snapshot",
                side_effect=AssertionError("no NOC call")), patch.object(
                noc_correlation, "_read_core_run", side_effect=AssertionError("no Core call")):
            response = self.request(authorized=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_no_source_never_contacts_core(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
                noc_correlation.noc_runtime, "read_signed_noc_snapshot",
                side_effect=noc_correlation.noc_runtime.NocSourceNotConfigured()), patch.object(
                noc_correlation, "_read_core_run", side_effect=AssertionError("no Core call")):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "noc_source_not_configured")

    def test_core_error_redacted(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
                noc_correlation.noc_runtime, "read_signed_noc_snapshot", return_value=noc_view()), patch.object(
                noc_correlation, "_read_core_run", side_effect=RuntimeError("SECRET-IN-CORE-ERROR")):
            response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_route_exposes_only_allowlisted_projection(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}), patch.object(
                noc_correlation.noc_runtime, "read_signed_noc_snapshot", return_value=noc_view()), patch.object(
                noc_correlation, "_read_core_run", return_value=core_run()):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "MATCHED_UNATTESTED")
        self.assertNotIn("private_payload", response.text)

    def test_core_endpoint_rejected_before_network(self):
        for url in ("https://evil.example", "http://user:pass@aiops2-core:810",
                    "http://aiops2-core:810/other", "http://127.0.0.1:810?x=1",
                    "http://127.0.0.1:5432"):
            with self.subTest(url=url), patch.dict(os.environ, {"CORE_URL": url}), patch.object(
                    noc_correlation.urllib.request, "build_opener",
                    side_effect=AssertionError("must not connect")):
                with self.assertRaises(ValueError):
                    noc_correlation._read_core_run("RUN-ACME-001")

    def test_run_path_injection_rejected_before_network(self):
        with patch.object(noc_correlation.urllib.request, "build_opener",
                          side_effect=AssertionError("must not connect")):
            with self.assertRaises(ValueError):
                noc_correlation._read_core_run("../etc/passwd")


    def test_core_read_is_get_only_and_bounded(self):
        import json
        class Response:
            headers = {"Content-Type": "application/json"}
            def __init__(self, url, body): self.url, self.body = url, body
            def geturl(self): return self.url
            def getcode(self): return 200
            def read(self, n): return self.body[:n]
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Opener:
            def open(self, req, timeout):
                self_req = req
                assert self_req.get_method() == "GET"
                assert timeout == 3
                assert self_req.full_url.endswith("/api/runs/RUN-ACME-001")
                return Response(req.full_url, json.dumps({"run": core_run()}).encode())
        with patch.dict(os.environ, {"CORE_URL": "http://aiops2-core:810"}), patch.object(
                noc_correlation.urllib.request, "build_opener", return_value=Opener()):
            self.assertEqual(noc_correlation._read_core_run("RUN-ACME-001")["mode"], "DEMO")

    def test_core_duplicate_json_keys_fail_closed(self):
        class Response:
            headers = {"Content-Type": "application/json"}
            def geturl(self): return "http://aiops2-core:810/api/runs/RUN-ACME-001"
            def getcode(self): return 200
            def read(self, n): return b'{"run":{},"run":{}}'
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Opener:
            def open(self, req, timeout): return Response()
        with patch.dict(os.environ, {"CORE_URL": "http://aiops2-core:810"}), patch.object(
                noc_correlation.urllib.request, "build_opener", return_value=Opener()):
            with self.assertRaises(ValueError):
                noc_correlation._read_core_run("RUN-ACME-001")


if __name__ == "__main__":
    unittest.main()
