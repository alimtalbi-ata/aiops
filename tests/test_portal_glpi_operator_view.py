"""Portal GLPI handoff: no invented ticket, no upstream, no role bypass."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-glpi-no-upstream-token"}):
    from portal import main, glpi_operator_view

from fastapi import HTTPException
from fastapi.testclient import TestClient

TOKEN = "ci-glpi-viewer-token"


class GlpiOperatorViewTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN, "AIOPS_PORTAL_OPERATOR_TOKEN": "ci-glpi-operator-token"})
        self.env.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def assert_security(self, response):
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])

    def test_single_portal_native_handoff_shell_is_accessible_and_synthetic(self):
        with patch.object(main, "get_json", side_effect=AssertionError("Core read")) as core, \
             patch.object(main, "post_json", side_effect=AssertionError("Core write")) as write:
            response = self.client.get("/itsm")
        self.assertEqual(response.status_code, 200)
        self.assert_security(response)
        self.assertIn('lang="fr"', response.text)
        self.assertIn('aria-label="Navigation Portal"', response.text)
        self.assertIn('data-story-provenance="SYNTHETIC"', response.text)
        self.assertIn("ACME P1 SAN→Payments", response.text)
        self.assertIn("SYNTHETIC", response.text)
        self.assertIn("UNKNOWN", response.text)
        self.assertIn("NOT_INSTALLED", response.text)
        self.assertIn('href="/#integrations"', response.text)
        self.assertIn("GLPI reste le système de référence", response.text)
        core.assert_not_called()
        write.assert_not_called()

    def test_native_inventory_roles_filters_and_no_browser_approval(self):
        page = self.client.get("/itsm").text
        for label in ("N1", "N2", "N3", "Manager", "P1", "P2", "P3", "P4",
                      "SLA", "OLA", "maintenance", "historique", "audit",
                      "Twin", "Evidence", "Analyst", "Critic", "Policy", "HITL",
                      "plugins", "formulaires", "templates", "règles métier"):
            with self.subTest(label=label):
                self.assertIn(label, page)
        self.assertIn('disabled aria-disabled="true"', page)
        self.assertNotIn("<form", page)
        self.assertNotIn("<button", page)
        self.assertNotIn("ticket_id", page)
        self.assertNotIn("evidence_id", page)
        self.assertNotIn(">CONNECTED<", page)
        self.assertIn("NOT_INSTALLED", page)

    def test_operator_queue_is_semantic_and_never_invents_tickets_or_sla(self):
        with patch.object(main, "get_json", side_effect=AssertionError("Core read")) as core, \
             patch.object(main, "post_json", side_effect=AssertionError("GLPI write")) as write:
            page = self.client.get("/itsm")
        self.assertEqual(page.status_code, 200)
        self.assert_security(page)
        self.assertIn('aria-labelledby="queue"', page.text)
        self.assertIn('aria-describedby="queue-unavailable"', page.text)
        self.assertIn('<caption>État de la file ITSM, sans enregistrement client</caption>', page.text)
        self.assertIn('colspan="4">UNKNOWN', page.text)
        self.assertIn("NOT_INSTALLED", page.text)
        self.assertIn("Aucun ticket ni compteur", page.text)
        self.assertIn("Calendrier de maintenance : UNKNOWN", page.text)
        self.assertNotIn("<button", page.text)
        self.assertNotIn("<form", page.text)
        core.assert_not_called()
        write.assert_not_called()
        api = self.client.get("/api/portal/itsm",
                              headers={"Authorization": "Bearer " + TOKEN,
                                       "X-Tenant-ID": "foreign", "X-GLPI-Profile": "manager"})
        self.assertEqual(api.status_code, 503)
        self.assertEqual(api.json()["connection_state"], "NOT_INSTALLED")
        self.assertNotIn("ticket_id", api.json())
        self.assert_security(api)

    def test_api_missing_invalid_and_unconfigured_bearer_fail_closed(self):
        for headers in ({}, {"Authorization": "Bearer incorrect"},
                        {"Authorization": "Basic " + TOKEN}):
            with self.subTest(headers=headers):
                response = self.client.get("/api/portal/itsm", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["state"], "UNAUTHORIZED")
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assert_security(response)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            response = self.client.get("/api/portal/itsm",
                                       headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assert_security(response)

    def test_valid_viewer_bearer_never_grants_tenant_or_ticket_read(self):
        with patch.object(main, "get_json", side_effect=AssertionError("Core called")) as core, \
             patch.object(main, "post_json", side_effect=AssertionError("GLPI write")) as write:
            response = self.client.get("/api/portal/itsm", headers={
                "Authorization": "Bearer " + TOKEN, "X-Tenant-ID": "foreign",
                "X-Actor-ID": "forged", "X-GLPI-Profile": "manager",
            })
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(data["connection_state"], "NOT_INSTALLED")
        self.assertEqual(data["source_freshness"], "UNKNOWN")
        self.assertFalse(data["tenant_acl_qualified"])
        self.assertFalse(data["glpi_write_enabled"])
        self.assertFalse(data["runtime_attested"])
        self.assertNotIn("ticket_id", data)
        self.assertNotIn("run_id", data)
        self.assertNotIn("actor", data)
        self.assertNotIn("tenant_id", data)
        self.assert_security(response)
        core.assert_not_called()
        write.assert_not_called()

    def test_forged_role_and_cross_tenant_headers_do_not_change_projection(self):
        base = self.client.get("/api/portal/itsm", headers={
            "Authorization": "Bearer " + TOKEN})
        for role in ("N1", "N2", "N3", "manager", "admin"):
            with self.subTest(role=role):
                response = self.client.get("/api/portal/itsm?ticket=42&role=" + role,
                    headers={"Authorization": "Bearer " + TOKEN,
                             "X-Tenant-ID": "other-tenant",
                             "X-Actor-ID": "forged", "X-GLPI-Profile": role})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), base.json())
                self.assert_security(response)

    def test_explicit_403_preserves_denial_and_security_headers(self):
        with patch.object(glpi_operator_view, "_require_portal_read_auth",
                          side_effect=HTTPException(403, "forbidden_tenant")):
            response = self.client.get("/api/portal/itsm", headers={
                "Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {
            "state": "UNAUTHORIZED", "reason": "forbidden_tenant"})
        self.assert_security(response)

    def test_glpi_fastpaths_are_mounted_but_viewer_token_cannot_use_them(self):
        expected = {
            ("POST", "/api/copilot/glpi-ticket/{ticket_id}"),
            ("POST", "/api/hitl/glpi-ticket/{ticket_id}/proposal"),
        }
        mounted = {
            (method, route.path)
            for route in main.app.routes
            if hasattr(route, "methods")
            for method in route.methods
        }
        self.assertTrue(expected.issubset(mounted))
        with patch.object(main.glpi_run_context, "GLPIClient",
                          side_effect=AssertionError("viewer token must be rejected before GLPI access")):
            for path in ("/api/copilot/glpi-ticket/1", "/api/hitl/glpi-ticket/1/proposal"):
                with self.subTest(path=path):
                    response = self.client.post(
                        path, headers={"Authorization": "Bearer " + TOKEN},
                        json={"question": "Analyse ce ticket.", "source_action_id": "CI-COLLECT-READONLY"},
                    )
                    self.assertEqual(response.status_code, 401)
                    self.assert_security(response)

    def test_no_glpi_mutation_routes(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = self.client.request(method.upper(), "/api/portal/itsm",
                                               json={"approve": True})
                self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()
