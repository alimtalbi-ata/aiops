import copy
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from ops.coordination.glpi_handoff_consumer import consume
from ops.coordination.itsm_handoff import build_handoff
from ops.coordination.core_case_collector import collect

CTX = {
    "schema": "aiops2-core-case-context-v1", "read_only": True,
    "source": "core_http_get", "checks": {"core_run": "PASS", "evidence_api": "PASS"},
    "run_id": "RUN-8CA56A39E58944F1",
    "incident_id": "INC-FS1250-AUTOGLPI-625916362ACD42C9",
    "run_status": "BLOCKED",
}
HANDOFF = build_handoff(CTX)


def ticket():
    return {"id": 201, "name": "Incident [" + CTX["incident_id"] + "]",
            "content": "<p>Run: " + CTX["run_id"] + "</p>"}


class GlpiConsumerTests(unittest.TestCase):
    def test_existing_reader_called_once_without_mutating_inputs(self):
        handoff, record = copy.deepcopy(HANDOFF), ticket()
        original = copy.deepcopy(record)
        reader = Mock(return_value=record)
        result = consume(handoff, 201, reader)
        reader.assert_called_once_with(201)
        self.assertEqual(result["status"], "READY_FOR_CORE_RECONCILIATION")
        self.assertTrue(result["glpi_readback_verified"])
        for field in ("core_xref_persisted", "worker_execution_authorized", "ticket_creation_authorized"):
            self.assertFalse(result[field])
        self.assertEqual(handoff, HANDOFF)
        self.assertEqual(record, original)

    def test_core_native_statuses_flow_to_existing_reader_without_execution(self):
        for status in ("CREATED", "WAITING", "RUNNING", "BLOCKED", "RESOLVED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                with patch("ops.coordination.core_case_collector._get_json", side_effect=[
                    {"run": {"run_id": CTX["run_id"], "incident_id": CTX["incident_id"],
                             "status": status}}, {"items": []}
                ]):
                    handoff = build_handoff(collect(CTX["run_id"]))
                result = consume(handoff, 201, Mock(return_value=ticket()))
                self.assertEqual(result["status"], "READY_FOR_CORE_RECONCILIATION")
                self.assertFalse(handoff["execution_authorized"])
                self.assertFalse(result["core_xref_persisted"])
                self.assertFalse(result["worker_execution_authorized"])
                self.assertEqual(handoff["policy_disposition"],
                                 "DENIED" if status == "BLOCKED" else "NOT_ESTABLISHED")

    def test_missing_existing_reader_holds(self):
        for reader in (None, "https://example.test", {}):
            with self.subTest(reader=reader):
                self.assertEqual(consume(HANDOFF, 201, reader)["reason"],
                                 "GLPI_EXISTING_READER_REQUIRED")

    def test_missing_or_prefix_only_markers_hold(self):
        for field, key in (("name", "incident_id"), ("content", "run_id")):
            for value in ("", CTX[key] + "-OTHER", "PREFIX-" + CTX[key], CTX[key] + "X"):
                with self.subTest(field=field, value=value):
                    record = ticket()
                    record[field] = value
                    result = consume(HANDOFF, 201, Mock(return_value=record))
                    self.assertEqual(result["reason"], "GLPI_CORRELATION_MARKERS_MISSING")

    def test_invalid_ticket_response_holds(self):
        for record in (None, [], {}, {**ticket(), "id": 202},
                       {**ticket(), "id": "201"}, {**ticket(), "id": True}):
            with self.subTest(record=record):
                self.assertEqual(consume(HANDOFF, 201, Mock(return_value=record))["reason"],
                                 "GLPI_TICKET_ID_MISMATCH")

    def test_reader_errors_preserve_hold_and_do_not_leak_secrets(self):
        for error, reason in ((HTTPError("redacted", 401, "secret", {}, None), "GLPI_AUTH_REQUIRED"),
                              (HTTPError("redacted", 403, "secret", {}, None), "GLPI_AUTH_REQUIRED"),
                              (HTTPError("redacted", 500, "secret", {}, None), "GLPI_HTTP_ERROR"),
                              (URLError("secret"), "GLPI_CONNECTION_ERROR"),
                              (TimeoutError("secret"), "GLPI_CONNECTION_ERROR"),
                              (ValueError("secret"), "GLPI_CONNECTION_ERROR")):
            with self.subTest(error=type(error), reason=reason):
                result = consume(HANDOFF, 201, Mock(side_effect=error))
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["status"], "HOLD")
                self.assertNotIn("secret", str(result))

    def test_authorization_and_identity_errors_prevent_read(self):
        invalid = [{**HANDOFF, k: True} for k in
                   ("execution_authorized", "execute_worker", "create_ticket_authorized")]
        invalid += [{**HANDOFF, "correlation_id": "OTHER"},
                    {**HANDOFF, "run_id": " " + CTX["run_id"]}]
        for handoff in invalid:
            reader = Mock()
            with self.assertRaises(ValueError):
                consume(handoff, 201, reader)
            reader.assert_not_called()
        for ticket_id in (0, -1, True, "201"):
            reader = Mock()
            with self.assertRaises(ValueError):
                consume(HANDOFF, ticket_id, reader)
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
