import os
import unittest
from unittest.mock import patch, Mock

from portal.glpi_client import GLPIClient, GLPIError


class GLPIPrivateFollowupTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GLPI_API_URL": "http://glpi/apirest.php",
            "GLPI_APP_TOKEN": "app-test-token",
            "GLPI_USER_TOKEN": "user-test-token",
        })
        self.env.start()
        self.client = GLPIClient()
        self.marker = "[AIOPS2-HITL-PROPOSAL:ACT-1234567890]"
        self.content = self.marker + "\nPROPOSED — approval required; execution disabled."

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def response(payload):
        r = Mock()
        r.raise_for_status.return_value = None
        r.json.return_value = payload
        r.content = b"{}"
        return r

    def test_existing_marker_is_idempotent_and_does_not_create_duplicate(self):
        with patch("portal.glpi_client.requests.get", side_effect=[
            self.response({"session_token": "session-1"}),
            self.response({}),
        ]) as get, patch("portal.glpi_client.requests.request",
                         return_value=self.response([{"id": 77, "content": self.content, "is_private": 1}])) as request:
            receipt = self.client.add_private_followup("1", self.marker, self.content)
        self.assertEqual(receipt, {"id": 77, "idempotent": True, "is_private": True})
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertIn("Ticket/1/ITILFollowup", request.call_args.args[1])

    def test_new_followup_is_private_and_uses_ticket_parent(self):
        with patch("portal.glpi_client.requests.get", side_effect=[
            self.response({"session_token": "session-1"}),
            self.response({}),
            self.response({"session_token": "session-2"}),
            self.response({}),
        ]), patch("portal.glpi_client.requests.request", side_effect=[
            self.response([]),
            self.response({"id": 88}),
        ]) as request:
            receipt = self.client.add_private_followup("1", self.marker, self.content)
        self.assertEqual(receipt, {"id": 88, "idempotent": False, "is_private": True})
        self.assertEqual(request.call_count, 2)
        payload = request.call_args_list[1].kwargs["json"]["input"]
        self.assertEqual(payload["itemtype"], "Ticket")
        self.assertEqual(payload["items_id"], 1)
        self.assertEqual(payload["is_private"], 1)
        self.assertIn(self.marker, payload["content"])

    def test_invalid_marker_or_public_content_is_refused(self):
        with self.assertRaises(ValueError):
            self.client.add_private_followup("1", "bad-marker", self.content)
        with self.assertRaises(ValueError):
            self.client.add_private_followup("1", self.marker, "not marked")

    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {"GLPI_APP_TOKEN": "", "GLPI_USER_TOKEN": ""}):
            client = GLPIClient()
        with self.assertRaises(GLPIError):
            client.list_ticket_followups("1")


if __name__ == "__main__":
    unittest.main()
