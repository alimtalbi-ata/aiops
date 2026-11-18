"""Portal usability layer endpoint and progressive enhancement contract."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-usability-test-token"}):
    from portal.main import app
from fastapi.testclient import TestClient


class PortalUsabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_home_loads_usability_asset_from_same_origin(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('/assets/portal-usability.js', page.text)
        self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])

    def test_usability_asset_is_local_and_not_cacheable(self):
        response = self.client.get("/assets/portal-usability.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["content-type"])
        self.assertIn("portal-workspace-nav", response.text)
        self.assertIn("portal-run-filter-input", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_dashboard_keeps_existing_safety_states_and_function_routes(self):
        page = self.client.get("/")
        for expected in (
            "UNKNOWN", "/itsm", "/demo/acme-impact", "/demo/explore-story",
            "portal-navigation.js", "portal-bootstrap.js", "portal-run-link.js",
        ):
            self.assertIn(expected, page.text)


    def test_noc_workspace_keeps_controls_and_explicit_initial_states(self):
        page = self.client.get("/")
        for expected in (
            'class="noc-workspace-summary"', 'class="noc-workspace-grid"',
            'UNKNOWN — corrélation à vérifier', 'NOT_TESTED — contrôle HTTP disponible',
            'DEMO — références synthétiques uniquement',
            'id="noc-token"', 'id="noc-result"', 'id="noc-grafana-result"',
            'id="noc-rag-result"', 'onclick="correlateNoc()"',
            'onclick="grafanaHealth()"', 'onclick="demoRag()"',
        ):
            self.assertIn(expected, page.text)



    def test_run_explorer_shows_ordered_model_not_observed_events(self):
        page = self.client.get("/runs/RUN-73AFC6FF9315376C")
        self.assertIn(page.status_code, (401, 503))
        self.assertIn('class="run-journey-grid"', page.text)
        self.assertEqual(page.text.count('class="run-step-number"'), 8)
        self.assertIn("Étape 01", page.text)
        self.assertIn("Étape 08", page.text)
        self.assertIn("pas une chronologie observée", page.text)
        self.assertIn("NOT VERIFIED", page.text)


    def test_incident_explorer_does_not_present_unqualified_inventory(self):
        page = self.client.get("/")
        self.assertIn('id="incident-explorer"', page.text)
        self.assertIn("UNKNOWN — inventaire des incidents non autorisé", page.text)
        self.assertIn("Ce statut ne signifie pas", page.text)
        self.assertIn('placeholder="Identifiant, service ou équipement" disabled', page.text)
        self.assertIn("<select disabled><option>Toutes les criticités", page.text)



    def test_future_incident_policy_denies_cross_tenant_and_unknown_roles(self):
        from portal.incident_read_policy import IncidentReadPrincipal, may_read_incident
        for role in ("N1", "N2", "N3", "MANAGER"):
            principal = IncidentReadPrincipal("operator-1", "tenant-a", role)
            self.assertTrue(may_read_incident(principal, "tenant-a"))
            self.assertFalse(may_read_incident(principal, "tenant-b"))
            self.assertFalse(may_read_incident(principal, None))
        for principal in (None, {"tenant": "tenant-a"},
                          IncidentReadPrincipal("", "tenant-a", "N1"),
                          IncidentReadPrincipal("operator-1", "tenant-a", "ADMIN"),
                          IncidentReadPrincipal("operator-1", "*", "N1")):
            self.assertFalse(may_read_incident(principal, "tenant-a"))


    def test_operator_session_prototype(self):
        from portal.operator_session import OperatorSessions
        from portal.incident_read_policy import IncidentReadPrincipal
        now = [0]
        sessions = OperatorSessions(clock=lambda: now[0])
        principal = IncidentReadPrincipal("operator-1", "tenant-a", "N1")
        token = sessions.issue(principal)
        self.assertEqual(sessions.resolve(token), principal)
        self.assertIsNone(sessions.resolve("invalid"))
        sessions.revoke(token)
        self.assertIsNone(sessions.resolve(token))
        token = sessions.issue(principal)
        now[0] += 900
        self.assertIsNone(sessions.resolve(token))
        token = sessions.issue(principal)
        for _ in range(35):
            now[0] += 800
            self.assertEqual(sessions.resolve(token), principal)
        now[0] += 800
        self.assertIsNone(sessions.resolve(token))
        with self.assertRaises(ValueError):
            sessions.issue(IncidentReadPrincipal("operator-1", "tenant-a", "UNKNOWN"))


    def test_session_incident_authorization_rechecks_membership(self):
        from portal.operator_access import authorize_incident_read
        from portal.operator_session import OperatorSessions
        from portal.incident_read_policy import IncidentReadPrincipal
        sessions = OperatorSessions()
        principal = IncidentReadPrincipal("operator-1", "tenant-a", "N1")
        token = sessions.issue(principal)
        current = lambda subject, tenant: principal
        self.assertTrue(authorize_incident_read(sessions, token, "tenant-a", current))
        self.assertFalse(authorize_incident_read(sessions, token, "tenant-b", current))
        def unavailable(subject, tenant):
            raise RuntimeError("authority unavailable")
        self.assertFalse(authorize_incident_read(sessions, token, "tenant-a", unavailable))
        self.assertFalse(authorize_incident_read(sessions, token, "tenant-a",
                                                lambda subject, tenant: None))
        self.assertIsNone(sessions.resolve(token))
        token = sessions.issue(principal)
        changed = IncidentReadPrincipal("operator-1", "tenant-a", "N2")
        self.assertFalse(authorize_incident_read(sessions, token, "tenant-a",
                                                lambda subject, tenant: changed))
        self.assertIsNone(sessions.resolve(token))



if __name__ == "__main__":
    unittest.main()
