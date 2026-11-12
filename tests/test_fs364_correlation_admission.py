"""Offline FS.364 idempotency contract; no GLPI/Temporal I/O."""
from dataclasses import replace
import unittest
from app.core.fs364_correlation_admission import admit_correlation
from app.core.fs364_outbox_envelope import ResumeEnvelope


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.env = ResumeEnvelope(
            "alert:fs:92", "INC-001", "RUN-001", "EVD-001",
            "tenant-demo", "DEMO", 147, "key-001", "v1", "p1"
        )

    def test_new_then_exact_replay(self):
        first = admit_correlation(self.env, None)
        self.assertEqual(first.status, "NEW")
        for _ in range(5):
            replay = admit_correlation(self.env, first.envelope)
            self.assertEqual(replay.status, "REPLAY")
            self.assertIs(replay.envelope, first.envelope)

    def test_same_key_different_identity_is_conflict(self):
        for field, value in (
            ("alert_fingerprint", "alert:other"), ("incident_id", "INC-002"),
            ("run_id", "RUN-002"), ("evidence_id", "EVD-002"),
            ("state_version", "v2"), ("policy_version", "p2"),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    admit_correlation(replace(self.env, **{field: value}), self.env).status,
                    "CONFLICT",
                )

    def test_fail_closed_mode_ticket_and_bad_keys(self):
        for change in (
            {"mode": "LIVE"}, {"ticket_id": 146}, {"ticket_id": True},
            {"idempotency_key": "key with space"}, {"tenant_id": ""},
            {"evidence_id": "EVD\\nBAD"},
        ):
            with self.subTest(change=change):
                self.assertEqual(admit_correlation(replace(self.env, **change), None).status, "CONFLICT")

    def test_unrelated_existing_record_is_not_claimed(self):
        other = replace(self.env, idempotency_key="another")
        self.assertEqual(admit_correlation(self.env, other).status, "CONFLICT")


if __name__ == "__main__":
    unittest.main()
