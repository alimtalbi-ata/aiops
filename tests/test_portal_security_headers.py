"""Isolated ASGI/HTTP contract tests; no real upstream service is contacted."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-unit-only-portal-security-headers"}, clear=False):
    from portal.main import app
from portal.portal_security_headers import SECURITY_HEADERS


class PortalSecurityHeadersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def assert_hardened(self, response):
        for name, expected in SECURITY_HEADERS.items():
            with self.subTest(header=name, status=response.status_code):
                self.assertEqual(response.headers.get(name), expected)

    def test_health_success_is_not_cacheable_or_frameable(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["component"], "portal")
        self.assert_hardened(response)

    def test_components_preserve_read_model_semantics(self):
        response = self.client.get("/api/portal/components")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["runtime_verified"])
        self.assert_hardened(response)

    def test_unknown_path_cannot_be_cached_or_embedded(self):
        response = self.client.get("/api/portal/path-that-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assert_hardened(response)

    def test_disallowed_method_is_hardened(self):
        response = self.client.post("/api/portal/components")
        self.assertEqual(response.status_code, 405)
        self.assert_hardened(response)

    def test_invalid_request_is_hardened(self):
        response = self.client.post("/api/copilot", content=b"not-json",
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assert_hardened(response)


if __name__ == "__main__":
    unittest.main()
