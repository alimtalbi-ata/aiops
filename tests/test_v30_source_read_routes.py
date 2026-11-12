"""Negative tests: routes cannot leak tenant data or trigger upstream I/O."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from portal.main import app

class V30SourceReadRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_anonymous_refused_before_any_source_read(self):
        for path in ("/prometheus", "/databases", "/cmdb",
                     "/api/portal/prometheus", "/api/portal/databases",
                     "/api/portal/cmdb"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn(response.status_code, (401, 403))
                self.assertIsNone(response.json().get("data"))
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_authenticated_shared_bearer_is_not_tenant_acl(self):
        with patch("portal.v30_source_read_routes._require_portal_read_auth", return_value=None):
            for path in ("/prometheus", "/databases", "/cmdb"):
                with self.subTest(path=path):
                    response = self.client.get(path, headers={"Authorization": "Bearer synthetic-test-only"},
                                               params={"tenant_id": "other", "query": "up", "sql": "SELECT 1",
                                                       "mode": "DEMO"})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["state"], "UNKNOWN")
                    self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
                    self.assertIsNone(response.json()["data"])
                    self.assertFalse(response.json()["tenant_acl_qualified"])

    def test_no_mutating_methods(self):
        for path in ("/prometheus", "/databases", "/cmdb"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 405)

if __name__ == "__main__":
    unittest.main()
