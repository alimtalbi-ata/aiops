import os
import unittest
from unittest.mock import patch

# Portal and shared HTTP client intentionally fail closed without configured secrets.
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "test-internal-token-not-a-real-secret")
os.environ.setdefault("AIOPS_PORTAL_OPERATOR_TOKEN", "test-operator-token-not-a-real-secret")

from portal.main import CopilotQuestion, require_operator, safe_upstream
from fastapi import HTTPException


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


if __name__ == "__main__":
    unittest.main()
