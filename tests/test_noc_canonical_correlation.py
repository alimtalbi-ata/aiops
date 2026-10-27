"""Offline contract tests only: no actual Checkmk/Thruk/Core or Grafana in this suite."""
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

    def test_live_mode_is_never_claimed_attested(self):
        result = noc_correlation.correlate(noc_view(), core_run("LIVE"))
        self.assertEqual(result["data_classification"], "LIVE_MODE_UNATTESTED")
        self.assertFalse(result["production_qualified"])

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
                    "http://aiops2-core:810/other", "http://127.0.0.1:810?x=1"):
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


if __name__ == "__main__":
    unittest.main()
