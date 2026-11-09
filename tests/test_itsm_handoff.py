import unittest
from ops.coordination.itsm_handoff import build_handoff

CTX = {
    "schema": "aiops2-core-case-context-v1",
    "read_only": True, "source": "core_http_get",
    "checks": {"core_run": "PASS", "evidence_api": "PASS"},
    "run_id": "RUN-8CA56A39E58944F1",
    "incident_id": "INC-FS1250-AUTOGLPI-625916362ACD42C9",
    "run_status": "BLOCKED",
}


class HandoffTests(unittest.TestCase):
    def test_blocked_run_creates_tracking_handoff_not_execution(self):
        result = build_handoff(CTX)
        self.assertEqual(result["policy_disposition"], "DENIED")
        self.assertEqual(result["requested_operation"], "UPSERT_INCIDENT_TRACKING")
        self.assertFalse(result["execute_worker"])
        self.assertFalse(result["create_ticket_authorized"])
        self.assertEqual(result["delivery_status"], "NOT_SENT")
        self.assertFalse(result["glpi_readback_verified"])

    def test_idempotency_stable_for_same_incident(self):
        first = build_handoff(CTX)
        second = build_handoff({**CTX, "run_id": "RUN-OTHER"})
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_missing_evidence_fails_closed(self):
        with self.assertRaises(ValueError):
            build_handoff({**CTX, "checks": {"core_run": "PASS"}})

    def test_unknown_status_fails_closed(self):
        with self.assertRaises(ValueError):
            build_handoff({**CTX, "run_status": "UNKNOWN"})

    def test_success_does_not_implicitly_authorize_worker(self):
        result = build_handoff({**CTX, "run_status": "SUCCESS"})
        self.assertEqual(result["policy_disposition"], "NOT_ESTABLISHED")
        self.assertFalse(result["execute_worker"])


if __name__ == "__main__":
    unittest.main()
