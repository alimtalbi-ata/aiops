"""Unit and HTTP contract tests only: fake fetchers are NOT real integration services."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "ci-test-internal-token-not-production")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.operator_read import build_operator_snapshot, require_role, router

VIEWER = "v" * 40
OPERATOR = "o" * 40
ENV = {"AIOPS_PORTAL_READ_TOKEN": VIEWER, "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR}
RESPONSES = {
    "/api/incidents": {"items": [{"incident_id": "INC-1", "title": "P1 SAN", "severity": "P1",
                                   "state": "OPEN", "synthetic": False, "payload": {"secret": "NEVER"}}]},
    "/api/runs": {"items": [{"run_id": "RUN-1", "mode": "DEMO", "status": "BLOCKED",
                             "private_token": "NEVER"}]},
    "/api/evidence?limit=50": {"items": [{"evidence_id": "EVD-1", "source": "thruk",
                                         "claim": "alarm", "payload_hash": "a" * 64,
                                         "payload": {"password": "NEVER"}}]},
}

class PortalOperatorReadTests(unittest.TestCase):
    def test_viewer_cannot_fetch_evidence(self):
        calls = []
        def fetch(base, path):
            calls.append(path)
            return RESPONSES[path]
        result = build_operator_snapshot(fetch, "core", "evidence", "viewer")
        self.assertEqual(result["states"]["evidence"], "FORBIDDEN_BY_ROLE")
        self.assertNotIn("/api/evidence?limit=50", calls)
        self.assertEqual(result["states"]["incidents"], "READABLE_UNVERIFIED")
        self.assertFalse(result["runtime_authenticated"])
        self.assertFalse(result["live_remediation_authorized"])

    def test_operator_gets_redacted_metadata(self):
        result = build_operator_snapshot(lambda base, path: RESPONSES[path],
                                         "core", "evidence", "operator")
        self.assertEqual(set(result["states"].values()), {"READABLE_UNVERIFIED"})
        self.assertNotIn("payload", result["resources"]["evidence"]["items"][0])
        self.assertNotIn("private_token", result["resources"]["runs"]["items"][0])
        self.assertNotIn("payload", result["resources"]["incidents"]["items"][0])
        self.assertEqual(result["provenance"], "UNATTESTED_UPSTREAM_API_READ")

    def test_all_upstreams_fail_closed(self):
        def fail(base, path):
            raise TimeoutError("internal secret in exception")
        result = build_operator_snapshot(fail, "core", "evidence", "operator")
        self.assertEqual(set(result["states"].values()), {"UNKNOWN"})
        self.assertTrue(all(value is None for value in result["resources"].values()))
        self.assertNotIn("internal secret", str(result))

    def test_partial_failure_is_isolated(self):
        def fetch(base, path):
            if path == "/api/runs":
                raise ConnectionError("down")
            return RESPONSES[path]
        result = build_operator_snapshot(fetch, "core", "evidence", "operator")
        self.assertEqual(result["states"]["runs"], "UNKNOWN")
        self.assertEqual(result["states"]["incidents"], "READABLE_UNVERIFIED")

    def test_invalid_payloads_fail_closed(self):
        bad = [None, {"items": {}}, {"items": [{"run_id": "../secret"}]},
               {"items": [{"run_id": "RUN-1", "version": {"malicious": True}}]},
               {"items": [{"run_id": "RUN-1", "overall_confidence": float("nan")}]},
               {"items": [{"run_id": "RUN-1"}] * 101}]
        for value in bad:
            with self.subTest(value=str(value)[:60]):
                result = build_operator_snapshot(
                    lambda base, path: value if path == "/api/runs" else RESPONSES[path],
                    "core", "evidence", "operator")
                self.assertEqual(result["states"]["runs"], "UNKNOWN")

    def test_invalid_roles_rejected(self):
        with self.assertRaises(ValueError):
            build_operator_snapshot(lambda *_: {}, "core", "evidence", "admin")

    def test_auth_missing_weak_or_duplicate_configuration(self):
        from fastapi import HTTPException
        for env in ({}, {"AIOPS_PORTAL_READ_TOKEN": "short"},
                    {"AIOPS_PORTAL_READ_TOKEN": VIEWER, "AIOPS_PORTAL_OPERATOR_TOKEN": VIEWER}):
            with self.subTest(env=env), self.assertRaises(HTTPException) as ctx:
                require_role("Bearer " + VIEWER, env)
            self.assertEqual(ctx.exception.status_code, 503)

    def test_auth_roles_and_invalid_token(self):
        from fastapi import HTTPException
        self.assertEqual(require_role("Bearer " + VIEWER, ENV), "viewer")
        self.assertEqual(require_role("Bearer " + OPERATOR, ENV), "operator")
        for header in (None, "Basic " + VIEWER, "Bearer wrong", "Bearer " + VIEWER + "\n"):
            with self.subTest(header=header), self.assertRaises(HTTPException) as ctx:
                require_role(header, ENV)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_http_denied_before_fetch(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch.dict(os.environ, ENV), patch("shared.http.get_json") as upstream:
            response = client.get("/api/portal/operator/snapshot")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["cache-control"], "no-store")
            upstream.assert_not_called()

    def test_http_operator_contract(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch.dict(os.environ, ENV), patch("shared.http.get_json",
                                               side_effect=lambda base, path: RESPONSES[path]):
            response = client.get("/api/portal/operator/snapshot",
                                  headers={"Authorization": "Bearer " + OPERATOR})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["states"]["evidence"], "READABLE_UNVERIFIED")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertNotIn("NEVER", response.text)

if __name__ == "__main__":
    unittest.main()
