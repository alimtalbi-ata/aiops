"""Security regression: Golden DEMO must never mutate Core without operator auth.

These are in-process HTTP contract tests, NOT live Core/Temporal integration.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-only-" + "z" * 48}):
    from portal.main import app
from portal.portal_command_auth import require_demo_operator

OPERATOR = "operator-credential-" + "x" * 44
VIEWER = "viewer-credential-" + "y" * 44
client = TestClient(app)


class PortalDemoAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_unconfigured_operator_fails_closed_without_core_calls(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_OPERATOR_TOKEN": ""}):
            with patch("portal.main.post_json") as upstream:
                response = client.post("/api/demo", headers={"Authorization": "Bearer " + OPERATOR})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["cache-control"], "no-store")
                upstream.assert_not_called()

    def test_missing_token_rejected_before_core(self):
        with patch("portal.main.post_json") as upstream:
            response = client.post("/api/demo")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
            upstream.assert_not_called()

    def test_wrong_token_rejected_before_core(self):
        with patch("portal.main.post_json") as upstream:
            response = client.post("/api/demo", headers={"Authorization": "Bearer " + "z" * 40})
            self.assertEqual(response.status_code, 401)
            upstream.assert_not_called()

    def test_viewer_cannot_trigger_demo(self):
        with patch("portal.main.post_json") as upstream:
            response = client.post("/api/demo", headers={"Authorization": "Bearer " + VIEWER})
            self.assertEqual(response.status_code, 401)
            upstream.assert_not_called()

    def test_ambiguous_roles_fail_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": OPERATOR}):
            with patch("portal.main.post_json") as upstream:
                response = client.post("/api/demo", headers={"Authorization": "Bearer " + OPERATOR})
                self.assertEqual(response.status_code, 503)
                upstream.assert_not_called()

    def test_weak_operator_config_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_OPERATOR_TOKEN": "demo"}):
            with patch("portal.main.post_json") as upstream:
                response = client.post("/api/demo", headers={"Authorization": "Bearer demo"})
                self.assertEqual(response.status_code, 503)
                upstream.assert_not_called()

    def test_invalid_bearer_scheme_rejected(self):
        with patch("portal.main.post_json") as upstream:
            response = client.post("/api/demo", headers={"Authorization": "Basic " + OPERATOR})
            self.assertEqual(response.status_code, 401)
            upstream.assert_not_called()

    def test_valid_operator_only_creates_synthetic_demo_run(self):
        with patch("portal.main.post_json", side_effect=[
            {"incident_id": "INC-1"}, {"run_id": "RUN-1"}, {"state": "SIMULATED"}
        ]) as upstream:
            response = client.post("/api/demo", headers={"Authorization": "Bearer " + OPERATOR})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(upstream.call_count, 3)
            incident = upstream.call_args_list[0].args[2]
            run = upstream.call_args_list[1].args[2]
            self.assertIs(incident["synthetic"], True)
            self.assertEqual(run["mode"], "DEMO")
            self.assertEqual(upstream.call_args_list[2].args[1], "/api/runs/RUN-1/execute")

    def test_health_remains_readable_without_token(self):
        self.assertEqual(client.get("/health").status_code, 200)

    def test_token_is_not_placed_in_homepage(self):
        with patch("portal.main.read_portal_snapshot", return_value={
            "dashboard": None, "runs": None, "twin": None, "states": {}
        }):
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn('id="demo-token"', response.text)
            self.assertNotIn(OPERATOR, response.text)
            self.assertNotIn(VIEWER, response.text)


if __name__ == "__main__":
    unittest.main()
