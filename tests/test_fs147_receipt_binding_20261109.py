"""Negative contract tests: provenance receipt fields are fingerprint-bound."""
import unittest
from datetime import datetime, timezone

from worker.fs147_observation_gate import admit_observation


class ObservationReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 3, 20, tzinfo=timezone.utc)
        self.envelope = {
            "tenant_id": "tenant-a", "ticket_id": 147, "run_id": "run-a",
            "source": "fs-lab", "access_mode": "read-only",
            "provenance_verified": True, "source_event_id": "event-a",
            "observed_at": "2026-11-09T03:19:00Z",
            "received_at": "2026-11-09T03:19:30Z",
            "evidence": {"available": True, "count": 2},
        }

    def admit(self):
        return admit_observation(
            self.envelope, now=self.now, expected_run_id="run-a",
            expected_tenant_id="tenant-a", expected_ticket_id=147,
        )

    def test_same_receipt_replay_is_deterministic(self):
        first = self.admit()
        self.assertEqual(first["status"], "ACCEPTED")
        self.assertEqual(first, self.admit())

    def test_distinct_transport_receipt_time_changes_fingerprint(self):
        first = self.admit()
        self.envelope["received_at"] = "2026-11-09T03:19:40Z"
        second = self.admit()
        self.assertEqual(second["status"], "ACCEPTED")
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_transport_mode_must_remain_read_only(self):
        self.envelope["access_mode"] = "read-write"
        result = self.admit()
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["fingerprint"])

    def test_future_or_reversed_receipt_time_is_unknown(self):
        for received in ("2026-11-09T03:21:00Z", "2026-11-09T03:18:00Z"):
            with self.subTest(received=received):
                self.envelope["received_at"] = received
                self.assertEqual(self.admit()["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
