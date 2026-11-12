"""Negative fs-lab bridge admission checks (pure, no network/GLPI writes)."""
import unittest
from datetime import datetime, timezone
from worker.fs147_observation_gate import admit_observation


class ObservationIdentitySafety(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 2, 24, tzinfo=timezone.utc)
        self.envelope = {
            "run_id": "run-147", "tenant_id": "tenant-a", "ticket_id": 147,
            "source": "fs-lab", "access_mode": "read-only",
            "provenance_verified": True, "source_event_id": "evt-1",
            "observed_at": "2026-11-09T02:23:30Z",
            "received_at": "2026-11-09T02:23:40Z",
            "evidence": {"availability": 0.8},
        }

    def admit(self, **kwargs):
        return admit_observation(self.envelope, now=self.now,
            expected_run_id=kwargs.get("run_id", "run-147"),
            expected_tenant_id=kwargs.get("tenant_id", "tenant-a"),
            expected_ticket_id=147,
            max_age_seconds=kwargs.get("max_age_seconds", 180))

    def test_blank_contexts_fail_closed_even_when_envelope_matches(self):
        for field in ("run_id", "tenant_id"):
            for bad in ("", "   "):
                with self.subTest(field=field, bad=bad):
                    envelope = dict(self.envelope)
                    envelope[field] = bad
                    self.envelope = envelope
                    receipt = self.admit(**{field: bad})
                    self.assertEqual(receipt["status"], "UNKNOWN")
                    self.assertEqual(receipt["reason"], "INVALID_IDENTITY")
                    self.assertIsNone(receipt["fingerprint"])
                    self.envelope[field] = "run-147" if field == "run_id" else "tenant-a"

    def test_nonfinite_freshness_is_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=repr(bad)):
                receipt = self.admit(max_age_seconds=bad)
                self.assertEqual(receipt["status"], "UNKNOWN")
                self.assertEqual(receipt["reason"], "INVALID_FRESHNESS_POLICY")
                self.assertIsNone(receipt["fingerprint"])

    def test_valid_receipt_is_deterministic_and_not_action_authority(self):
        a = self.admit()
        self.assertEqual(a["status"], "ACCEPTED")
        self.assertEqual(a, self.admit())
        self.assertEqual(len(a["fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
