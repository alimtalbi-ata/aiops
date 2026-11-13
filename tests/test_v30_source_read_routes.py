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
            for path in ("/prometheus", "/databases", "/cmdb",
                         "/api/portal/prometheus", "/api/portal/databases",
                         "/api/portal/cmdb"):
                with self.subTest(path=path):
                    response = self.client.get(path, headers={"Authorization": "Bearer synthetic-test-only"})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["state"], "UNKNOWN")
                    self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
                    self.assertIsNone(response.json()["data"])

    def test_query_parameters_rejected_after_authentication(self):
        paths = ("/prometheus", "/databases", "/cmdb",
                 "/api/portal/prometheus", "/api/portal/databases", "/api/portal/cmdb")
        parameters = (("query", "up"), ("sql", "SELECT 1"),
                      ("tenant_id", "other"), ("mode", "DEMO"),
                      ("query", "up", "query", "down"), ("unexpected", "value"))
        with patch("portal.v30_source_read_routes._require_portal_read_auth", return_value=None):
            for path in paths:
                for parameter in parameters:
                    with self.subTest(path=path, parameter=parameter):
                        pairs = list(zip(parameter[::2], parameter[1::2]))
                        response = self.client.get(path, params=pairs)
                        self.assertEqual(response.status_code, 400)
                        self.assertEqual(response.json()["state"], "BLOCKED")
                        self.assertEqual(response.json()["reason"], "INVALID_PARAMETERS")
                        self.assertIsNone(response.json()["data"])
                        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_anonymous_query_parameters_do_not_bypass_authentication(self):
        for path in ("/prometheus", "/databases", "/cmdb",
                     "/api/portal/prometheus", "/api/portal/databases",
                     "/api/portal/cmdb"):
            with self.subTest(path=path):
                response = self.client.get(path, params={"query": "up"})
                self.assertIn(response.status_code, (401, 403))
                self.assertEqual(response.json()["state"], "BLOCKED")
                self.assertIsNone(response.json()["data"])

    def test_no_mutating_methods(self):
        paths = ("/prometheus", "/databases", "/cmdb",
                 "/api/portal/prometheus", "/api/portal/databases",
                 "/api/portal/cmdb")
        for path in paths:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(path=path, method=method):
                    response = self.client.request(method, path,
                                                   params={"query": "up", "sql": "SELECT 1"})
                    self.assertEqual(response.status_code, 405)

if __name__ == "__main__":
    unittest.main()
