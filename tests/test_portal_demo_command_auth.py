"""Portal DEMO command boundary: a browser bearer is not tenant authority.

Offline TestClient only. No Core, GLPI, Temporal or LIVE calls.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-" + "i" * 48}):
    from portal import main

VIEWER = "viewer-" + "v" * 48
OPERATOR = "operator-" + "o" * 48
INTERNAL = "internal-" + "i" * 48


class DemoOperatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
            "AIOPS_INTERNAL_TOKEN": INTERNAL,
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def post(self, token=None, headers=None, json=None):
        if headers is None:
            headers = {"Authorization": "Bearer " + token} if token else {}
        return self.client.post("/api/demo", headers=headers, json=json)

    def assert_security(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])

    def test_invalid_browser_tokens_401_and_zero_upstream(self):
        for headers in ({}, {"Authorization": "Basic " + OPERATOR},
                        {"Authorization": "Bearer " + VIEWER},
                        {"Authorization": "Bearer " + INTERNAL},
                        {"Authorization": "Bearer " + "x" * 40},
                        {"Authorization": "Bearer " + OPERATOR + " extra"}):
            with self.subTest(headers=headers), patch.object(
                    main, "post_json", side_effect=AssertionError("Core write")) as upstream:
                r = self.post(headers=headers)
                self.assertEqual(r.status_code, 401)
                self.assertEqual(r.headers["www-authenticate"], "Bearer")
                self.assert_security(r)
                upstream.assert_not_called()

    def test_unconfigured_or_colliding_operator_token_503_without_upstream(self):
        for changes in ({"AIOPS_PORTAL_OPERATOR_TOKEN": ""},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": "demo"},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": VIEWER},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": INTERNAL},
                        {"AIOPS_PORTAL_READ_TOKEN": OPERATOR}):
            with self.subTest(changes=changes), patch.dict(os.environ, changes), patch.object(
                    main, "post_json", side_effect=AssertionError("Core write")) as upstream:
                r = self.post(OPERATOR)
                self.assertEqual(r.status_code, 503)
                self.assert_security(r)
                upstream.assert_not_called()

    def test_valid_operator_token_is_not_actor_tenant_authority(self):
        with patch.object(main, "post_json", side_effect=AssertionError("Core write")) as upstream:
            r = self.post(OPERATOR)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json(), {
            "state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED",
            "connection_state": "UNKNOWN", "source": "DEMO_CORE_MUTATION_NOT_AUTHORIZED",
            "source_freshness": "UNKNOWN", "live_remediation_authorized": False,
        })
        self.assert_security(r)
        self.assertNotIn("run_id", r.json())
        self.assertNotIn("incident_id", r.json())
        upstream.assert_not_called()

    def test_forged_actor_tenant_role_and_run_never_enable_write(self):
        headers = {"Authorization": "Bearer " + OPERATOR, "X-Actor-ID": "admin",
                   "X-Tenant-ID": "other-tenant", "X-GLPI-Profile": "manager",
                   "X-Portal-Run-ID": "RUN-FOREIGN"}
        with patch.object(main, "post_json", side_effect=AssertionError("Core write")) as upstream:
            r = self.post(headers=headers, json={"actor_id": "admin",
                "tenant_id": "other-tenant", "run_id": "RUN-FOREIGN",
                "approve": True, "mode": "LIVE"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assert_security(r)
        upstream.assert_not_called()

    def test_cross_tenant_and_forged_identifiers_indistinguishable(self):
        with patch.object(main, "post_json", side_effect=AssertionError("Core write")) as upstream:
            baseline = self.post(OPERATOR)
            for rid in ("RUN-FOREIGN-TENANT", "RUN-FORGED-999", "../etc/passwd"):
                with self.subTest(rid=rid):
                    r = self.post(OPERATOR, json={"run_id": rid})
                    self.assertEqual(r.status_code, 503)
                    self.assertEqual(r.json(), baseline.json())
                    self.assert_security(r)
            upstream.assert_not_called()

    def test_no_secret_or_upstream_error_disclosed(self):
        with patch.object(main, "post_json",
                          side_effect=RuntimeError("private-core-host-secret")) as upstream:
            r = self.post(OPERATOR)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private-core-host-secret", r.text)
        upstream.assert_not_called()

    def test_anonymous_home_disables_demo_launch_and_stays_synthetic(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="demo-token"', r.text)
        self.assertIn('disabled aria-disabled="true"', r.text)
        self.assertIn("Golden DEMO — désactivé", r.text)
        self.assertNotIn('onclick="demo()"', r.text)
        self.assertNotIn(OPERATOR, r.text)
        self.assertNotIn("localStorage", r.text)
        self.assert_security(r)
        self.assertEqual(self.client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
