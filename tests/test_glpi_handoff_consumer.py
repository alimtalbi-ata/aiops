import unittest
from unittest.mock import patch

from ops.coordination.glpi_handoff_consumer import consume
from ops.coordination.itsm_handoff import build_handoff

CTX = {
    "schema": "aiops2-core-case-context-v1", "read_only": True,
    "source": "core_http_get", "checks": {"core_run": "PASS", "evidence_api": "PASS"},
    "run_id": "RUN-8CA56A39E58944F1",
    "incident_id": "INC-FS1250-AUTOGLPI-625916362ACD42C9",
    "run_status": "BLOCKED",
}
HANDOFF = build_handoff(CTX)


class GlpiConsumerTests(unittest.TestCase):
    def test_real_identity_readback_prepares_only_core_proposal(self):
        ticket = {"id": 201, "name": "Incident " + CTX["incident_id"],
                  "content": "Run " + CTX["run_id"]}
        with patch("ops.coordination.glpi_handoff_consumer._ticket_get", return_value=ticket) as get:
            result = consume(HANDOFF, 201, "http://127.0.0.1:8080", "test-session")
        self.assertEqual(result["status"], "READY_FOR_CORE_RECONCILIATION")
        self.assertTrue(result["glpi_readback_verified"])
        self.assertFalse(result["core_xref_persisted"])
        self.assertFalse(result["worker_execution_authorized"])
        self.assertEqual(get.call_count, 1)

    def test_ticket_without_incident_marker_holds(self):
        with patch("ops.coordination.glpi_handoff_consumer._ticket_get",
                   return_value={"id": 201, "name": CTX["run_id"], "content": ""}):
            result = consume(HANDOFF, 201, "http://127.0.0.1:8080", "test-session")
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "GLPI_CORRELATION_MARKERS_MISSING")

    def test_ticket_id_mismatch_holds(self):
        with patch("ops.coordination.glpi_handoff_consumer._ticket_get",
                   return_value={"id": 199, "name": CTX["incident_id"], "content": CTX["run_id"]}):
            result = consume(HANDOFF, 201, "http://127.0.0.1:8080", "test-session")
        self.assertEqual(result["reason"], "GLPI_TICKET_ID_MISMATCH")

    def test_no_credentials_no_api_call(self):
        with patch("ops.coordination.glpi_handoff_consumer._ticket_get") as get:
            result = consume(HANDOFF, 201, "http://127.0.0.1:8080", None)
        self.assertEqual(result["reason"], "GLPI_AUTH_REQUIRED")
        get.assert_not_called()

    def test_execution_authorization_is_rejected(self):
        with self.assertRaises(ValueError):
            consume({**HANDOFF, "execute_worker": True}, 201, "http://127.0.0.1:8080", "token")

    def test_invalid_ticket_id_is_rejected(self):
        with self.assertRaises(ValueError):
            consume(HANDOFF, 0, "http://127.0.0.1:8080", "token")


if __name__ == "__main__":
    unittest.main()
