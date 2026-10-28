"""Offline Golden DEMO write-gate and canonical identity tests; no Core/GLPI contacted."""
import copy
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from portal import acme_golden_demo as golden


TOKEN = "unit-test-acme-demo-write-token-32-chars"
CORE = "http://aiops2-core:810"


def core_stub(calls, *, wrong_incident=False, wrong_mode=False, wrong_receipt=False):
    def send(base, path, payload):
        assert base == CORE
        calls.append((path, payload))
        if path == "/api/incidents":
            return {"incident_id": "INC-OTHER" if wrong_incident else
                    "INC-ACME-DEMO-SAN-001", "synthetic": True}
        if path == "/api/runs":
            return {"run_id": "RUN-ACME-001", "mode": "LIVE" if wrong_mode else "DEMO"}
        if path == "/api/runs/RUN-ACME-001/execute":
            return {"run_id": "RUN-OTHER" if wrong_receipt else "RUN-ACME-001"}
        raise AssertionError("unexpected upstream call")
    return send


class GoldenDemoTests(unittest.TestCase):
    def test_fixture_bound_launch_is_deterministic_and_not_attested(self):
        calls = []
        first = golden.launch_acme_golden_demo(core_stub(calls), CORE)
        self.assertEqual(first["run_id"], "RUN-ACME-001")
        self.assertEqual(first["canonical_incident_id"], "INC-ACME-DEMO-SAN-001")
        self.assertEqual(first["fixture_incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(first["fixture_impact_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(first["mode"], "DEMO")
        self.assertIsNone(first["ticket_id"])
        self.assertFalse(first["runtime_attested"])
        self.assertFalse(first["live_remediation_authorized"])
        self.assertEqual([path for path, _ in calls], [
            "/api/incidents", "/api/runs", "/api/runs/RUN-ACME-001/execute"])
        self.assertTrue(calls[0][1]["synthetic"])
        self.assertEqual(calls[0][1]["payload"]["fixture_sha256"], first["fixture_sha256"])
        self.assertEqual(calls[1][1]["incident_id"], first["canonical_incident_id"])
        self.assertEqual(calls[1][1]["mode"], "DEMO")
        self.assertEqual(calls[1][1]["scenario_id"], "SCN-GOLDEN-PAYMENT-P1")
        self.assertEqual(first, golden.launch_acme_golden_demo(core_stub([]), CORE))

    def test_wrong_incident_stops_before_run_creation(self):
        calls = []
        with self.assertRaises(ValueError):
            golden.launch_acme_golden_demo(core_stub(calls, wrong_incident=True), CORE)
        self.assertEqual(len(calls), 1)

    def test_live_run_response_stops_before_execute(self):
        calls = []
        with self.assertRaises(ValueError):
            golden.launch_acme_golden_demo(core_stub(calls, wrong_mode=True), CORE)
        self.assertEqual(len(calls), 2)

    def test_wrong_receipt_is_not_reported_as_accepted(self):
        with self.assertRaises(ValueError):
            golden.launch_acme_golden_demo(core_stub([], wrong_receipt=True), CORE)

    def test_invalid_fixture_blocks_before_core_writes(self):
        calls = []
        model = golden.build_acme_impact_read_model()
        for mutation in ({"ticket_id": "123"}, {"runtime_attested": True},
                         {"live_remediation_authorized": True},
                         {"provenance": "LIVE"}, {"incident_id": "INC-OTHER"}):
            with self.subTest(mutation=mutation), patch.object(
                    golden, "build_acme_impact_read_model",
                    return_value={**model, **mutation}):
                with self.assertRaises(ValueError):
                    golden.launch_acme_golden_demo(core_stub(calls), CORE)
        self.assertEqual(calls, [])

    def test_demo_token_is_required_and_distinct_from_core_token(self):
        for configured, internal, expected in (
            ("", "internal-only", 503),
            ("short", "internal-only", 503),
            (TOKEN, TOKEN, 503),
            (TOKEN, "internal-only", 401),
        ):
            with self.subTest(configured=configured, expected=expected), patch.dict(
                    os.environ, {"AIOPS_PORTAL_DEMO_TOKEN": configured,
                                 "AIOPS_INTERNAL_TOKEN": internal}):
                with self.assertRaises(Exception) as caught:
                    golden.require_demo_auth(None)
                self.assertEqual(caught.exception.status_code, expected)

    def test_admin_token_aliases_cannot_authorize_demo(self):
        for alias in ("AIOPS_INTERNAL_TOKEN", "AIOPS_ADMIN_TOKEN", "ADMIN_TOKEN"):
            env = {"AIOPS_PORTAL_DEMO_TOKEN": TOKEN,
                   "AIOPS_INTERNAL_TOKEN": "different-internal-token",
                   "AIOPS_ADMIN_TOKEN": "different-admin-token",
                   "ADMIN_TOKEN": "different-core-token"}
            env[alias] = TOKEN
            with self.subTest(alias=alias), patch.dict(os.environ, env):
                with self.assertRaises(Exception) as caught:
                    golden.require_demo_auth("Bearer " + TOKEN)
                self.assertEqual(caught.exception.status_code, 503)

    def test_valid_token_and_invalid_token(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_DEMO_TOKEN": TOKEN,
                                     "AIOPS_INTERNAL_TOKEN": "internal-only"}):
            golden.require_demo_auth("Bearer " + TOKEN)
            for value in ("Bearer wrong", TOKEN, "Basic " + TOKEN, "Bearer " + TOKEN + "x"):
                with self.subTest(value=value), self.assertRaises(Exception) as caught:
                    golden.require_demo_auth(value)
                self.assertEqual(caught.exception.status_code, 401)

    def test_route_denies_before_core_and_does_not_leak_secret(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-only",
                                     "AIOPS_PORTAL_DEMO_TOKEN": TOKEN}):
            from portal.main import app
            with patch("portal.main.post_json", side_effect=AssertionError("no Core call")):
                response = TestClient(app).post("/api/demo", headers={
                    "Authorization": "Bearer wrong"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(TOKEN, response.text)

    def test_route_accepts_demo_only_and_returns_no_store(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-only",
                                     "AIOPS_PORTAL_DEMO_TOKEN": TOKEN}):
            from portal.main import app
            with patch("portal.main.post_json", side_effect=core_stub([])):
                response = TestClient(app).post("/api/demo", headers={
                    "Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["mode"], "DEMO")
        self.assertFalse(response.json()["runtime_attested"])

    def test_upstream_error_is_redacted(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-only",
                                     "AIOPS_PORTAL_DEMO_TOKEN": TOKEN}):
            from portal.main import app
            with patch("portal.main.post_json", side_effect=RuntimeError("SECRET-GLPI-FAIL")):
                response = TestClient(app).post("/api/demo", headers={
                    "Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET", response.text)


if __name__ == "__main__":
    unittest.main()
