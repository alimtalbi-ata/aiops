import os
import unittest

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "test-internal-token-not-a-real-secret")
os.environ.setdefault("AIOPS_PORTAL_OPERATOR_TOKEN", "test-operator-token-not-a-real-secret")

from fastapi import HTTPException
from fastapi.testclient import TestClient
from portal.main import (
    CopilotQuestion,
    app,
    require_operator,
    require_same_origin,
    safe_upstream,
)


class PortalAuthorizationTests(unittest.TestCase):
    def test_valid_bearer_token_is_accepted(self):
        self.assertTrue(require_operator("Bearer test-operator-token-not-a-real-secret"))

    def test_missing_authorization_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            require_operator(None)
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.headers["WWW-Authenticate"], "Bearer")

    def test_wrong_token_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            require_operator("Bearer wrong")
        self.assertEqual(caught.exception.status_code, 401)

    def test_wrong_scheme_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            require_operator("Basic test-operator-token-not-a-real-secret")
        self.assertEqual(caught.exception.status_code, 401)

    def test_empty_credential_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            require_operator("Bearer ")
        self.assertEqual(caught.exception.status_code, 401)

    def test_copilot_question_is_bounded(self):
        self.assertEqual(CopilotQuestion(question="status").question, "status")
        with self.assertRaises(ValueError):
            CopilotQuestion(question="")
        with self.assertRaises(ValueError):
            CopilotQuestion(question="x" * 4001)

    def test_upstream_exception_is_redacted(self):
        def fail():
            raise RuntimeError("internal host token=secret-value")
        with self.assertRaises(HTTPException) as caught:
            safe_upstream(fail)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("secret-value", caught.exception.detail)
        self.assertNotIn("internal host", caught.exception.detail)

    def test_successful_upstream_result_is_preserved(self):
        self.assertEqual(safe_upstream(lambda: {"status": "ok"}), {"status": "ok"})

    def test_cross_origin_is_rejected(self):
        request = type("RequestStub", (), {
            "headers": {"origin": "https://evil.example", "host": "localhost:7777"},
            "url": type("URLStub", (), {"scheme": "http"})(),
        })()
        with self.assertRaises(HTTPException) as caught:
            require_same_origin(request)
        self.assertEqual(caught.exception.status_code, 403)

    def test_same_origin_is_accepted(self):
        request = type("RequestStub", (), {
            "headers": {"origin": "http://localhost:7777", "host": "localhost:7777"},
            "url": type("URLStub", (), {"scheme": "http"})(),
        })()
        self.assertTrue(require_same_origin(request))

    def test_bootstrap_requires_operator_authentication(self):
        response = TestClient(app).get("/api/portal/bootstrap")
        self.assertEqual(response.status_code, 401)

    def test_homepage_is_only_a_login_shell_and_sets_security_headers(self):
        response = TestClient(app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertNotIn("DEMO-GOLDEN-PAYMENT", response.text)
        self.assertIn("Authenticate and load dashboard", response.text)

    def test_unauthenticated_copilot_post_is_rejected(self):
        response = TestClient(app).post("/api/copilot", json={"question": "status"})
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_demo_post_is_rejected(self):
        response = TestClient(app).post("/api/demo")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
