import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "i" * 64)
from fastapi.testclient import TestClient
from portal import main

OPERATOR = "p" * 64
DEMO_RUN = "RUN-DEMO123456"
LIVE_RUN = "RUN-LIVE123456"


class PortalHitlInboxTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_INTERNAL_TOKEN": "i" * 64,
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
        })
        self.env.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def auth(self):
        return {"Authorization": "Bearer " + OPERATOR}

    def test_hitl_page_is_static_and_does_not_read_core_for_anonymous_user(self):
        with patch.object(main, "get_json", side_effect=AssertionError("anonymous Core read")), \
             patch.object(main, "_get", side_effect=AssertionError("anonymous Core read")):
            response = self.client.get("/hitl")
        self.assertEqual(response.status_code, 200)
        self.assertIn("hitl-operator-token", response.text)
        self.assertIn("/assets/portal-hitl.js", response.text)
        self.assertNotIn("AIOPS_INTERNAL_TOKEN", response.text)
        self.assertNotIn("proposal_id", response.text)

    def test_inbox_requires_demo_operator_before_core_read(self):
        get = Mock(side_effect=AssertionError("unauthorized request must not call Core"))
        with patch.object(main, "get_json", get):
            response = self.client.get("/api/portal/hitl/inbox")
        self.assertEqual(response.status_code, 401)
        get.assert_not_called()

    def test_inbox_filters_every_proposal_to_verified_synthetic_run_mode(self):
        proposals = {"items": [
            {"proposal_id": "ACT-DEMO", "run_id": DEMO_RUN, "status": "PROPOSED",
             "risk_tier": "LOW", "action_type": "COLLECT_DIAGNOSTICS",
             "target_ci_id": "ACME-SYNTHETIC", "evidence_ids": ["EVD-1234567890"]},
            {"proposal_id": "ACT-LIVE", "run_id": LIVE_RUN, "status": "PROPOSED",
             "risk_tier": "HIGH", "action_type": "RESTART_SERVICE",
             "target_ci_id": "PROD-CI-01", "evidence_ids": ["EVD-1234567891"]},
        ]}
        def read(_base, path, **_kwargs):
            if path == "/api/proposals?status=PROPOSED&limit=100":
                return proposals
            if path == "/api/runs/" + DEMO_RUN:
                return {"run": {"run_id": DEMO_RUN, "mode": "DEMO"}}
            if path == "/api/runs/" + LIVE_RUN:
                return {"run": {"run_id": LIVE_RUN, "mode": "LIVE"}}
            raise AssertionError(path)
        with patch.object(main, "get_json", side_effect=read):
            response = self.client.get("/api/portal/hitl/inbox", headers=self.auth())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["proposal_id"], "ACT-DEMO")
        self.assertEqual(body["items"][0]["mode"], "SYNTHETIC_DEMO")
        self.assertFalse(body["items"][0]["execution_allowed"])
        self.assertFalse(body["items"][0]["approval_available"])
        self.assertNotIn("ACT-LIVE", response.text)
        self.assertNotIn("PROD-CI-01", response.text)

    def test_identity_simulator_proxy_requires_operator_token(self):
        post = Mock(side_effect=AssertionError("unauthorized simulator request must not call Core"))
        with patch.object(main, "post_json", post):
            response = self.client.post("/api/portal/hitl/simulator/token",
                                        json={"subject": "operator.alex"})
        self.assertEqual(response.status_code, 401)
        post.assert_not_called()

    def test_operator_can_issue_only_a_simulated_identity(self):
        with patch.object(main, "post_json", return_value={
            "access_token": "simulated-fixture-token", "simulated": True,
            "execution_allowed": False,
        }) as post:
            response = self.client.post("/api/portal/hitl/simulator/token",
                headers=self.auth(), json={"subject": "operator.alex"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["simulated"])
        self.assertFalse(response.json()["execution_allowed"])
        self.assertEqual(post.call_args.kwargs["token"], "i" * 64)

    def test_client_script_does_not_persist_or_inject_operator_token(self):
        response = self.client.get("/assets/portal-hitl.js")
        self.assertEqual(response.status_code, 200)
        for forbidden in ("localStorage", "sessionStorage", "document.cookie", "innerHTML"):
            self.assertNotIn(forbidden, response.text)
        self.assertIn("/api/portal/hitl/inbox", response.text)
        self.assertIn("Authorization", response.text)


if __name__ == "__main__":
    unittest.main()
