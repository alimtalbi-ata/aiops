"""In-process DEMO HTTP contracts; no Core, Temporal or LIVE integration."""
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
INCIDENT = {"incident_id": "INC-DEMO-GOLDEN-PAYMENT", "synthetic": True}
RUN = {"run_id": "RUN-1", "mode": "DEMO", "scenario_id": "SCN-GOLDEN-PAYMENT-P1"}
EXECUTED = {"run_id": "RUN-1", "workflow_id": "wf-demo-1"}

class DemoOperatorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
            "AIOPS_INTERNAL_TOKEN": INTERNAL})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def post(self, token=None, headers=None):
        if headers is None:
            headers = {"Authorization": "Bearer " + token} if token else {}
        return self.client.post("/api/demo", headers=headers)

    def test_denials_before_core(self):
        for headers in ({}, {"Authorization": "Basic " + OPERATOR},
                        {"Authorization": "Bearer " + VIEWER},
                        {"Authorization": "Bearer " + INTERNAL},
                        {"Authorization": "Bearer " + "x" * 40},
                        {"Authorization": "Bearer " + OPERATOR + " extra"}):
            with self.subTest(headers=headers), patch.object(main, "post_json") as upstream:
                r = self.post(headers=headers)
                self.assertEqual(r.status_code, 401)
                self.assertEqual(r.headers["cache-control"], "no-store")
                self.assertEqual(r.headers["www-authenticate"], "Bearer")
                upstream.assert_not_called()

    def test_missing_weak_or_colliding_operator_config_denied(self):
        for changes in ({"AIOPS_PORTAL_OPERATOR_TOKEN": ""},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": "demo"},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": VIEWER},
                        {"AIOPS_PORTAL_OPERATOR_TOKEN": INTERNAL},
                        {"AIOPS_PORTAL_READ_TOKEN": OPERATOR}):
            with self.subTest(changes=changes), patch.dict(os.environ, changes), patch.object(main, "post_json") as upstream:
                r = self.post(OPERATOR)
                self.assertEqual(r.status_code, 503)
                upstream.assert_not_called()

    def test_operator_submits_only_synthetic_demo_with_redacted_receipt(self):
        with patch.object(main, "post_json", side_effect=[
            INCIDENT, RUN, {**EXECUTED, "mode": "LIVE",
                            "runtime_authenticated": True, "secret": "never-leak"}]) as upstream:
            r = self.post(OPERATOR)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json(), {"state": "DEMO_SUBMITTED_UNVERIFIED", "mode": "DEMO",
                                   "run_id": "RUN-1", "runtime_authenticated": False,
                                   "live_remediation_authorized": False})
        self.assertEqual(upstream.call_count, 3)
        self.assertIs(upstream.call_args_list[0].args[2]["synthetic"], True)
        self.assertEqual(upstream.call_args_list[1].args[2]["mode"], "DEMO")
        self.assertEqual(upstream.call_args_list[2].args[1], "/api/runs/RUN-1/execute")

    def test_bad_incident_receipt_stops_before_run(self):
        for incident in ({}, {"incident_id": "../bad", "synthetic": True},
                         {"incident_id": "INC-OK", "synthetic": False}):
            with self.subTest(incident=incident), patch.object(main, "post_json", side_effect=[incident]) as upstream:
                self.assertEqual(self.post(OPERATOR).status_code, 503)
                self.assertEqual(upstream.call_count, 1)

    def test_bad_run_receipt_stops_before_execute(self):
        for run in ({}, {**RUN, "run_id": "../bad"}, {**RUN, "mode": "LIVE"},
                    {**RUN, "scenario_id": "OTHER"}, {**RUN, "run_id": "RUN-1/execute"}):
            with self.subTest(run=run), patch.object(main, "post_json", side_effect=[INCIDENT, run]) as upstream:
                self.assertEqual(self.post(OPERATOR).status_code, 503)
                self.assertEqual(upstream.call_count, 2)

    def test_bad_execute_receipt_is_unknown(self):
        for receipt in ({}, {"run_id": "RUN-OTHER"},
                        {"run_id": "RUN-1", "workflow_id": ""}):
            with self.subTest(receipt=receipt), patch.object(main, "post_json",
                side_effect=[INCIDENT, RUN, receipt]):
                r = self.post(OPERATOR)
                self.assertEqual(r.status_code, 503)
                self.assertEqual(r.json()["state"], "UNKNOWN")

    def test_upstream_exception_redacted(self):
        with patch.object(main, "post_json", side_effect=RuntimeError("private-host-secret")):
            r = self.post(OPERATOR)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("private-host-secret", r.text)

    def test_anonymous_shell_has_one_shot_input_without_secret(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="demo-token"', r.text)
        self.assertIn("credentials:'omit'", r.text)
        self.assertIn("DEMO_SUBMITTED_UNVERIFIED", r.text)
        self.assertNotIn(OPERATOR, r.text)
        self.assertNotIn("localStorage", r.text)
        self.assertEqual(self.client.get("/health").status_code, 200)
