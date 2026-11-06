import unittest
from dataclasses import replace

from app.core.fs364_delivery_receipt import DeliveryReceipt, ack_receipt_matches
from app.core.fs364_outbox_transition import OutboxRecord


class DeliveryReceiptTests(unittest.TestCase):
    def setUp(self):
        self.record = OutboxRecord("evt-1", 2, "CLAIMED", 1, "tenant-1", "key-1", 147, "DEMO")
        self.receipt = DeliveryReceipt("evt-1", "tenant-1", "key-1",
                                       "workflow-1", "signal-1", 147, "DEMO", True)

    def test_repeat_is_pure_and_deterministic(self):
        for _ in range(5):
            self.assertTrue(ack_receipt_matches(self.record, self.receipt, expected_revision=2))
        self.assertEqual(self.record.status, "CLAIMED")

    def test_identity_mismatch_fails_closed(self):
        for field, value in (("event_id", "other"), ("tenant_id", "other"),
                             ("idempotency_key", "other"), ("workflow_id", ""),
                             ("signal_id", "bad signal"), ("ticket_id", 146),
                             ("mode", "LIVE"), ("accepted", False),
                             ("accepted", 1)):
            with self.subTest(field=field, value=value):
                self.assertFalse(ack_receipt_matches(
                    self.record, replace(self.receipt, **{field: value}), expected_revision=2))

    def test_claim_revision_and_mode_are_required(self):
        for field, value in (("status", "ACKED"), ("status", "PENDING"),
                             ("revision", 3), ("attempt", 0),
                             ("ticket_id", 146), ("mode", "LIVE")):
            with self.subTest(field=field):
                self.assertFalse(ack_receipt_matches(
                    replace(self.record, **{field: value}), self.receipt, expected_revision=2))
        self.assertFalse(ack_receipt_matches(self.record, self.receipt, expected_revision=True))
        self.assertFalse(ack_receipt_matches(self.record, self.receipt, expected_revision=3))


if __name__ == "__main__":
    unittest.main()
