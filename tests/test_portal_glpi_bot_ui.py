import os
import unittest
from pathlib import Path

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "portal-glpi-bot-test-internal-token")
from fastapi.testclient import TestClient
from portal.main import app


class PortalGLPIBotUITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_copilot_page_exposes_glpi_operator_interaction_without_secrets(self):
        response = self.client.get("/copilot")
        self.assertEqual(response.status_code, 200)
        for marker in ("Assistant AIOps", "Identifiant du ticket GLPI",
                       "Jeton opérateur DEMO", "Interroger AIOps sur ce ticket",
                       "Créer la proposition HITL", "Aucune approbation"):
            self.assertIn(marker, response.text)
        for forbidden in ("AIOPS_INTERNAL_TOKEN", "GLPI_USER_TOKEN", "GLPI_APP_TOKEN"):
            self.assertNotIn(forbidden, response.text)

    def test_client_asset_is_same_origin_and_does_not_persist_tokens(self):
        response = self.client.get("/assets/portal-glpi-bot.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("textContent", response.text)
        self.assertIn("/api/copilot/glpi-ticket/", response.text)
        self.assertIn("/api/hitl/glpi-ticket/", response.text)
        for forbidden in ("localStorage", "sessionStorage", "document.cookie", "innerHTML"):
            self.assertNotIn(forbidden, response.text)


if __name__ == "__main__":
    unittest.main()
