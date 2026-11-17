"""In-process ASGI HTTP qualification of the existing Portal Workbench route.

No sockets, Core, Worker, Twin, GLPI or browser. TestClient only.
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from portal.main import app


class WorkbenchPortalHttpTests(unittest.TestCase):
    def test_public_get_is_safe_no_go_and_no_service_io(self):
        with patch("portal.main.get_json", side_effect=AssertionError("Core/Twin access")), \
             patch("portal.main.post_json", side_effect=AssertionError("mutation")), \
             TestClient(app) as client:
            response = client.get("/acme-workbench")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        for expected in ("NO_GO", "SIMULATION UNIQUEMENT",
                         "REMEDIATION_EFFECT", "LEARN", "ITSM / Worker",
                         "NON IMPLÉMENTÉ", "NON VÉRIFIÉ",
                         "Parcours de qualification", "Identité / ACL",
                         "Core / Twin", "Audit / Learn",
                         "Ce que prouvent les tests CI"):
            self.assertIn(expected, response.text)
        self.assertNotIn("Bearer ", response.text)
        self.assertNotIn("ACME_CORE_SERVICE_TOKEN", response.text)

    def test_query_cannot_change_static_status_or_inject_html(self):
        with patch("portal.main.get_json", side_effect=AssertionError("service access")), \
             patch("portal.main.post_json", side_effect=AssertionError("mutation")), \
             TestClient(app) as client:
            response = client.get("/acme-workbench",
                                  params={"status": "GO", "tenant": "<script>alert(1)</script>",
                                          "viewer_acl_verified": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("NO_GO", response.text)
        self.assertNotIn("<script>alert(1)</script>", response.text)

    def test_static_workbench_response_is_not_cacheable_or_frameable(self):
        with patch("portal.main.get_json", side_effect=AssertionError("service read")), \
             patch("portal.main.post_json", side_effect=AssertionError("service write")), \
             TestClient(app) as client:
            response = client.get("/acme-workbench")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn("geolocation=()", response.headers["permissions-policy"])
        self.assertNotIn("set-cookie", response.headers)

    def test_route_is_get_only(self):
        with TestClient(app) as client:
            response = client.post("/acme-workbench", json={"approve": True})
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()
