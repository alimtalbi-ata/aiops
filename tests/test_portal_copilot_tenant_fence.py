"""Fail-closed legacy Copilot proxy regression (in-process, no Core/Copilot calls)."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "synthetic-test-only-internal-token"}):
    from portal import main

from fastapi.testclient import TestClient

TOKEN = "synthetic-portal-read-token"


class CopilotTenantFenceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def _assert_security(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_missing_and_invalid_bearers_deny_before_upstream(self):
        for headers in ({}, {"Authorization": "Basic " + TOKEN},
                        {"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + TOKEN + " trailing"}):
            with self.subTest(headers=headers), patch.object(
                main, "post_json", side_effect=AssertionError("Copilot called")
            ) as upstream:
                response = self.client.post("/api/copilot", json={"question": "sensitive"},
                                            headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "invalid_portal_read_token"})
                self._assert_security(response)
                upstream.assert_not_called()

    def test_unconfigured_read_auth_returns_503_without_upstream(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            main, "post_json", side_effect=AssertionError("Copilot called")
        ) as upstream:
            response = self.client.post("/api/copilot", json={"question": "sensitive"},
                                        headers={"Authorization": "Bearer " + TOKEN})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": "portal_read_auth_not_configured"})
            self._assert_security(response)
            upstream.assert_not_called()

    def test_valid_shared_token_does_not_authorize_tenant_copilot(self):
        with patch.object(main, "post_json", side_effect=AssertionError("Copilot called")) as upstream:
            response = self.client.post("/api/copilot", json={
                "question": "Show foreign tenant ticket", "actor": "forged", "tenant_id": "other"
            }, headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["state"], "UNKNOWN")
        self.assertEqual(data["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(data["source"], "COPILOT_NOT_TENANT_AUTHORIZED")
        self.assertEqual(data["source_freshness"], "UNKNOWN")
        self.assertNotIn("ticket", data)
        self.assertNotIn("actor", data)
        self.assertNotIn("tenant_id", data)
        self._assert_security(response)
        upstream.assert_not_called()

    def test_home_copilot_renders_http_error_and_is_noncacheable(self):
        with patch.object(main, "get_json", side_effect=AssertionError("Core called")) as upstream:
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("HTTP '+r.status", response.text)
        self.assertIn("UNAUTHORIZED", response.text)
        self.assertIn("credentials:'omit'", response.text)
        self.assertIn("Copilot indisponible", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
