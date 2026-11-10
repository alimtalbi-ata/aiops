import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from portal import main


class GLPICopilotRouteCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_both_historical_paths_fail_closed_without_upstream_calls(self):
        paths = (
            "/api/copilot/ticket/201",
            "/api/copilot/glpi-ticket/201",
        )
        with patch.object(main, "_require_portal_read_auth"), \
             patch.object(main, "get_json", side_effect=AssertionError("Core read forbidden")), \
             patch.object(main, "post_json", side_effect=AssertionError("Copilot call forbidden")):
            for path in paths:
                with self.subTest(path=path):
                    response = self.client.post(
                        path, json={"question": "Analyse le ticket"}
                    )
                    self.assertEqual(response.status_code, 503)
                    body = response.json()
                    self.assertEqual(body["state"], "UNKNOWN")
                    self.assertFalse(body["glpi_read_performed"])
                    self.assertFalse(body["core_read_performed"])
                    self.assertFalse(body["copilot_query_performed"])
                    self.assertFalse(body["hitl_proposal_created"])
                    self.assertFalse(body["execution_allowed"])

    def test_authentication_precedes_ticket_validation(self):
        def deny(_authorization):
            raise HTTPException(status_code=401, detail="invalid_portal_read_token")

        with patch.object(main, "_require_portal_read_auth", side_effect=deny):
            response = self.client.post("/api/copilot/ticket/0201", json={})
        self.assertEqual(response.status_code, 401)

    def test_noncanonical_ticket_id_is_rejected_after_auth(self):
        with patch.object(main, "_require_portal_read_auth"):
            response = self.client.post("/api/copilot/ticket/0201", json={})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["reason"], "INVALID_GLPI_TICKET_ID")


if __name__ == "__main__":
    unittest.main()
