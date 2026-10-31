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
            "AIOPS_SYNTHETIC_DEMO_LAUNCH_ENABLED": "true",
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

    def test_valid_operator_launches_only_fixed_synthetic_scenario(self):
        receipts = [
            {"incident_id":"INC-DEMO-GOLDEN-1234567890","synthetic":True},
            {"run_id":"RUN-DEMO-123456","status":"CREATED","mode":"DEMO"},
            {"run_id":"RUN-DEMO-123456","workflow_id":"wf-demo-123","idempotent":False},
        ]
        with patch.object(main, "post_json", side_effect=receipts) as upstream:
            r = self.post(OPERATOR, headers={
                "Authorization":"Bearer " + OPERATOR,
                "Idempotency-Key":"customer-demo-retry-0001",
            })
        self.assertEqual(r.status_code, 202)
        data = r.json()
        self.assertEqual(data["state"], "STARTED")
        self.assertEqual(data["run_id"], "RUN-DEMO-123456")
        self.assertEqual(data["workflow_id"], "wf-demo-123")
        self.assertEqual(data["mode"], "DEMO")
        self.assertTrue(data["synthetic"])
        self.assertFalse(data["effect_allowed"])
        self.assertFalse(data["live_remediation_authorized"])
        self.assert_security(r)
        self.assertEqual(upstream.call_count, 3)
        incident_call, run_call, execute_call = upstream.call_args_list
        self.assertEqual(incident_call.args[1], "/api/incidents")
        self.assertTrue(incident_call.args[2]["synthetic"])
        self.assertEqual(incident_call.args[2]["severity"], "P1")
        self.assertEqual(incident_call.args[2]["service_id"], "ACME-SVC-PAYMENTS")
        self.assertEqual(run_call.args[1], "/api/runs")
        self.assertEqual(run_call.args[2]["mode"], "DEMO")
        self.assertEqual(run_call.args[2]["scenario_id"], "SCN-GOLDEN-PAYMENT-P1")
        self.assertEqual(execute_call.args[1], "/api/runs/RUN-DEMO-123456/execute")
        for call in upstream.call_args_list:
            self.assertEqual(call.kwargs["token"], INTERNAL)

    def test_forged_actor_tenant_role_and_run_payload_is_rejected(self):
        headers = {"Authorization": "Bearer " + OPERATOR, "X-Actor-ID": "admin",
                   "X-Tenant-ID": "other-tenant", "X-GLPI-Profile": "manager",
                   "X-Portal-Run-ID": "RUN-FOREIGN"}
        with patch.object(main, "post_json", side_effect=AssertionError("Core write")) as upstream:
            r = self.post(headers=headers, json={"actor_id": "admin",
                "tenant_id": "other-tenant", "run_id": "RUN-FOREIGN",
                "approve": True, "mode": "LIVE"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "synthetic_demo_payload_not_supported")
        self.assert_security(r)
        upstream.assert_not_called()

    def test_client_supplied_run_ids_are_rejected_not_selected(self):
        with patch.object(main, "post_json", side_effect=AssertionError("Core write")) as upstream:
            for rid in ("RUN-FOREIGN-TENANT", "RUN-FORGED-999", "../etc/passwd"):
                with self.subTest(rid=rid):
                    r = self.post(OPERATOR, json={"run_id": rid})
                    self.assertEqual(r.status_code, 422)
                    self.assert_security(r)
            upstream.assert_not_called()

    def test_idempotency_key_retries_resolve_to_same_run(self):
        receipts = [
            {"incident_id":"INC-DEMO-GOLDEN-1234567890","synthetic":True},
            {"run_id":"RUN-DEMO-123456","status":"CREATED","mode":"DEMO"},
            {"run_id":"RUN-DEMO-123456","workflow_id":"wf-demo-123","idempotent":False},
            {"incident_id":"INC-DEMO-GOLDEN-1234567890","synthetic":True},
            {"run_id":"RUN-DEMO-123456","status":"CREATED","mode":"DEMO"},
            {"run_id":"RUN-DEMO-123456","workflow_id":"wf-demo-123","idempotent":True},
        ]
        headers={"Authorization":"Bearer " + OPERATOR,"Idempotency-Key":"stable-demo-key-0001"}
        with patch.object(main, "post_json", side_effect=receipts) as upstream:
            first=self.post(headers=headers)
            second=self.post(headers=headers)
        self.assertEqual(first.json()["run_id"], second.json()["run_id"])
        self.assertEqual(upstream.call_args_list[0].args[2]["external_id"],
                         upstream.call_args_list[3].args[2]["external_id"])
        self.assertEqual(upstream.call_args_list[1].args[2]["idempotency_key"],
                         upstream.call_args_list[4].args[2]["idempotency_key"])
        self.assertTrue(second.json()["idempotent"])

    def test_no_secret_or_upstream_error_disclosed(self):
        with patch.object(main, "post_json",
                          side_effect=RuntimeError("private-core-host-secret")) as upstream:
            r = self.post(OPERATOR)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private-core-host-secret", r.text)
        upstream.assert_called_once()

    def test_framework_generated_405_and_422_also_have_security_headers(self):
        # FastAPI emits these responses before reaching route auth handlers.
        for method, path, kwargs, expected in (
            ("get", "/api/demo", {}, 405),
            ("put", "/api/portal/itsm", {}, 405),
            ("get", "/api/copilot", {}, 405),
            ("post", "/api/copilot", {"json": ["not", "an", "object"]}, 422),
        ):
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, expected)
                self.assert_security(response)

    def test_anonymous_home_disables_demo_launch_and_stays_synthetic(self):
        with patch.dict(os.environ, {"AIOPS_SYNTHETIC_DEMO_LAUNCH_ENABLED":"false"}):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Lancer DEMO (désactivé)", r.text)
        self.assertNotIn('id="demo-token"', r.text)
        self.assertNotIn(OPERATOR, r.text)
        self.assertNotIn("localStorage", r.text)
        self.assert_security(r)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_configured_home_exposes_one_shot_demo_control_without_secret(self):
        r=self.client.get("/")
        self.assertEqual(r.status_code,200)
        self.assertIn('id="demo-token" type="password"',r.text)
        self.assertIn('id="launch-demo"',r.text)
        self.assertIn('/assets/demo-launch.js',r.text)
        self.assertNotIn(OPERATOR,r.text)
        js=self.client.get('/assets/demo-launch.js')
        self.assertEqual(js.status_code,200)
        self.assertIn('credentials: "omit"',js.text)
        self.assertNotIn('localStorage',js.text)


if __name__ == "__main__":
    unittest.main()
