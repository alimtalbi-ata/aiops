"""Offline HTTP contracts: no actual Copilot, NIM, Ollama or LIVE service contacted."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-" + "i" * 48}):
    from portal.main import app
from portal.portal_copilot_guard import project_copilot_response

VIEWER = "viewer-" + "v" * 48
OPERATOR = "operator-" + "o" * 48
INTERNAL = "internal-" + "i" * 48
QUESTION = "What evidence supports this incident?"
RESULT = {"answer": "UNKNOWN without verified evidence.", "question": QUESTION,
          "sources": ["core:/api/dashboard"], "confidence": 0.6,
          "limitations": ["Not runtime attested."]}
client = TestClient(app)


class CopilotPortalAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_READ_TOKEN": VIEWER,
            "AIOPS_PORTAL_OPERATOR_TOKEN": OPERATOR,
            "AIOPS_INTERNAL_TOKEN": INTERNAL,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def call(self, token=None, payload=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        return client.post("/api/copilot", headers=headers,
                           json=payload if payload is not None else {"question": QUESTION})

    def test_missing_token_does_not_contact_upstream(self):
        with patch("portal.main.post_json") as upstream:
            response = self.call()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["www-authenticate"], "Bearer")
        upstream.assert_not_called()

    def test_wrong_and_internal_tokens_rejected(self):
        for token in ("z" * 48, INTERNAL):
            with self.subTest(token=token[:4]), patch("portal.main.post_json") as upstream:
                self.assertEqual(self.call(token).status_code, 401)
                upstream.assert_not_called()

    def test_weak_and_missing_configuration_fail_closed(self):
        for bad in ("", "short", "x" * 257):
            with self.subTest(bad=bad[:4]), patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": bad}):
                with patch("portal.main.post_json") as upstream:
                    self.assertEqual(self.call(VIEWER).status_code, 503)
                    upstream.assert_not_called()

    def test_ambiguous_role_tokens_fail_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_OPERATOR_TOKEN": VIEWER}):
            with patch("portal.main.post_json") as upstream:
                self.assertEqual(self.call(VIEWER).status_code, 503)
                upstream.assert_not_called()

    def test_internal_token_reuse_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": INTERNAL}):
            with patch("portal.main.post_json") as upstream:
                self.assertEqual(self.call(INTERNAL).status_code, 503)
                upstream.assert_not_called()

    def test_viewer_and_operator_can_read_but_never_authorize_live(self):
        for token in (VIEWER, OPERATOR):
            with self.subTest(role=token[:4]), patch("portal.main.post_json", return_value=RESULT) as upstream:
                response = self.call(token)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["state"], "READABLE_UNVERIFIED")
                self.assertIs(response.json()["runtime_authenticated"], False)
                self.assertIs(response.json()["live_remediation_authorized"], False)
                upstream.assert_called_once_with(app_module_copilot(), "/api/copilot/query",
                                                 {"question": QUESTION})

    def test_rejects_prompt_control_fields_and_invalid_questions(self):
        for payload in (
            {"question": QUESTION, "mode": "LIVE"},
            {"question": QUESTION, "tools": [{"type": "function"}]},
            {"question": ""}, {"question": "  "}, {"question": 7},
            {"question": "a" * 2049}, {"question": "bad\x00question"},
        ):
            with self.subTest(payload=str(payload)[:40]), patch("portal.main.post_json") as upstream:
                self.assertEqual(self.call(VIEWER, payload).status_code, 422)
                upstream.assert_not_called()

    def test_rejects_basic_auth_scheme(self):
        with patch("portal.main.post_json") as upstream:
            response = client.post("/api/copilot", headers={"Authorization": "Basic " + VIEWER},
                                   json={"question": QUESTION})
        self.assertEqual(response.status_code, 401)
        upstream.assert_not_called()

    def test_upstream_failure_is_unknown_not_leaked(self):
        with patch("portal.main.post_json", side_effect=RuntimeError("private service url")):
            response = self.call(VIEWER)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("private service url", response.text)

    def test_untrusted_upstream_claims_are_stripped(self):
        with patch("portal.main.post_json", return_value={
            **RESULT, "live_remediation_authorized": True, "runtime_authenticated": True,
            "api_key": "sensitive", "production_qualified": True
        }):
            response = self.call(VIEWER)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api_key", response.json())
        self.assertNotIn("production_qualified", response.json())
        self.assertIs(response.json()["live_remediation_authorized"], False)

    def test_bad_upstream_schema_and_question_mismatch_unknown(self):
        for data in (None, {}, {"answer": "ok"}, {**RESULT, "question": "different"},
                     {**RESULT, "confidence": float("nan")}, {**RESULT, "confidence": True}):
            with self.subTest(data=str(data)[:50]), patch("portal.main.post_json", return_value=data):
                response = self.call(VIEWER)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_home_token_not_rendered_and_health_stays_public(self):
        with patch("portal.main.read_portal_snapshot", return_value={
            "dashboard": None, "runs": None, "twin": None, "states": {}
        }):
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="copilot-token"', response.text)
        self.assertNotIn(VIEWER, response.text)
        self.assertNotIn(OPERATOR, response.text)
        self.assertEqual(client.get("/health").status_code, 200)


def app_module_copilot():
    from portal.main import COPILOT
    return COPILOT


if __name__ == "__main__":
    unittest.main()
