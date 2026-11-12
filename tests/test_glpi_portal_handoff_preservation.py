"""Preserve existing GLPI Portal handoff and Copilot UI contracts fail-closed.

These tests do not claim the legacy ticket-to-Copilot workflow is restored.
They lock the existing navigation and prevent accidental upstream calls until
server-derived actor/tenant ACL and canonical xref are qualified.
"""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from portal import main


class GLPIPortalHandoffPreservationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_existing_itsm_handoff_page_remains_available_without_upstream_io(self):
        with patch("portal.glpi_operator_view._require_portal_read_auth",
                   side_effect=AssertionError("anonymous shell must not authenticate")), \
             patch("portal.glpi_client.GLPIClient") as client:
            response = self.client.get("/itsm")
        self.assertEqual(response.status_code, 200)
        self.assertIn("GLPI / ITSM", response.text)
        self.assertIn('href="/"', response.text)
        self.assertEqual(client.call_count, 0)

    def test_existing_itsm_status_requires_auth_and_never_reads_glpi_or_core(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "test-viewer-token"}), \
             patch("portal.glpi_client.GLPIClient",
                   side_effect=AssertionError("GLPI read forbidden")), \
             patch("portal.glpi_operator_view.get_json",
                   side_effect=AssertionError("Core read forbidden")):
            denied = self.client.get("/api/portal/itsm")
            self.assertEqual(denied.status_code, 401)
            allowed_bearer = self.client.get(
                "/api/portal/itsm",
                headers={"Authorization": "Bearer test-viewer-token"},
            )
            forged_scope = self.client.get(
                "/api/portal/itsm",
                headers={
                    "Authorization": "Bearer test-viewer-token",
                    "X-Actor-ID": "admin",
                    "X-Tenant-ID": "tenant-production",
                    "X-GLPI-Entity-ID": "0",
                    "X-Role": "superuser",
                },
            )
        for response in (allowed_bearer, forged_scope):
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertFalse(response.json()["tenant_acl_qualified"])
        self.assertEqual(forged_scope.json(), allowed_bearer.json())

    def test_existing_generic_copilot_ui_endpoint_remains_fail_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "test-viewer-token"}), \
             patch("portal.main.post_json",
                   side_effect=AssertionError("Copilot upstream call forbidden")):
            denied = self.client.post("/api/copilot", headers={
                "Authorization": "Bearer wrong-token",
            })
            self.assertEqual(denied.status_code, 401)
            response = self.client.post("/api/copilot", headers={
                "Authorization": "Bearer test-viewer-token",
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
