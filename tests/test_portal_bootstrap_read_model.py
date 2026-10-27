"""ASGI contract tests for degraded, bounded, read-only portal bootstrap."""
from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Synthetic test-only credential for the shared HTTP adapter import; all calls
# made by these tests are patched and no backend/network is contacted.
with patch.dict(
    os.environ,
    {"AIOPS_INTERNAL_TOKEN": "synthetic-ci-only-token", "AIOPS_ADMIN_TOKEN": ""},
):
    from portal import main  # noqa: E402


class PortalBootstrapReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth_env = patch.dict(
            os.environ, {"AIOPS_PORTAL_READ_TOKEN": "synthetic-portal-read-token"}
        )
        cls.auth_env.start()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.auth_env.stop()

    def test_bootstrap_fails_closed_without_or_with_invalid_read_token(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            response = self.client.get("/api/portal/bootstrap")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "portal_read_auth_not_configured")

        response = self.client.get(
            "/api/portal/bootstrap",
            headers={"Authorization": "Bearer wrong-synthetic-token"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid_portal_read_token")

    def test_all_sources_are_read_independently_with_bounded_no_retry_calls(self):
        payloads = {
            (main.CORE, "/api/dashboard"): {"open_incidents": 2},
            (main.CORE, "/api/runs"): {"items": [{"run_id": "RUN-SYNTHETIC-001"}]},
            (main.TWIN, "/api/twin/summary"): {"nodes": 7},
        }
        calls = []

        def fake_get_json(base, path, **kwargs):
            calls.append((base, path, kwargs))
            return payloads[(base, path)]

        with patch.object(main, "get_json", side_effect=fake_get_json), patch.object(
            main, "post_json", side_effect=AssertionError("bootstrap must be read-only")
        ):
            response = self.client.get("/api/portal/bootstrap", headers={"Authorization": "Bearer synthetic-portal-read-token"})

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["dashboard"], payloads[(main.CORE, "/api/dashboard")])
        self.assertEqual(result["runs"], payloads[(main.CORE, "/api/runs")])
        self.assertEqual(result["twin"], payloads[(main.TWIN, "/api/twin/summary")])
        self.assertEqual(
            result["_portal"],
            {
                "schema": "aiops.portal-bootstrap-readmodel.v1",
                "status": "COMPLETE",
                "unavailable_sources": [],
                "source_mode": "BOUNDED_READ_ONLY_UPSTREAM_HTTP",
                "timeout_seconds": 3,
                "retry_count": 0,
                "upstream_provenance": "UNATTESTED_UPSTREAM_READS",
                "operator_authentication": "ENFORCED_DEDICATED_BEARER_TOKEN",
                "runtime_attested": False,
                "live_remediation_authorized": False,
            },
        )
        self.assertEqual(len(calls), 3)
        self.assertEqual(
            {(base, path) for base, path, _ in calls},
            set(payloads),
        )
        self.assertTrue(
            all(
                kwargs == {"timeout": 3, "retries": 0}
                for _, _, kwargs in calls
            )
        )

    def test_one_upstream_failure_degrades_only_that_source_and_redacts_exception(self):
        def fake_get_json(base, path, **kwargs):
            if path == "/api/dashboard":
                raise RuntimeError("SECRET_INTERNAL_URL_AND_TOKEN")
            if path == "/api/runs":
                return {"items": []}
            if path == "/api/twin/summary":
                return {"nodes": 4}
            raise AssertionError("unexpected upstream path")

        with patch.object(main, "get_json", side_effect=fake_get_json), patch.object(
            main, "post_json", side_effect=AssertionError("bootstrap must be read-only")
        ):
            response = self.client.get("/api/portal/bootstrap")

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(
            result["dashboard"],
            {
                "status": "UNKNOWN",
                "source": "UPSTREAM_UNAVAILABLE",
                "error_code": "READ_FAILED",
            },
        )
        self.assertEqual(result["runs"], {"items": []})
        self.assertEqual(result["twin"], {"nodes": 4})
        self.assertEqual(result["_portal"]["status"], "DEGRADED")
        self.assertEqual(result["_portal"]["unavailable_sources"], ["dashboard"])
        self.assertNotIn("SECRET_INTERNAL_URL_AND_TOKEN", response.text)
        self.assertNotIn(main.CORE, response.text)

    def test_non_object_upstream_payload_is_not_promoted_as_valid_snapshot(self):
        payloads = {
            "/api/dashboard": {"open_incidents": 1},
            "/api/runs": ["unexpected", "array"],
            "/api/twin/summary": {"nodes": 4},
        }

        def fake_get_json(base, path, **kwargs):
            return payloads[path]

        with patch.object(main, "get_json", side_effect=fake_get_json):
            response = self.client.get("/api/portal/bootstrap")

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(
            result["runs"],
            {
                "status": "UNKNOWN",
                "source": "UPSTREAM_INVALID_RESPONSE",
                "error_code": "NON_OBJECT_JSON",
            },
        )
        self.assertEqual(result["_portal"]["status"], "DEGRADED")
        self.assertEqual(result["_portal"]["unavailable_sources"], ["runs"])
        self.assertIs(result["_portal"]["runtime_attested"], False)
        self.assertIs(result["_portal"]["live_remediation_authorized"], False)


if __name__ == "__main__":
    unittest.main()
