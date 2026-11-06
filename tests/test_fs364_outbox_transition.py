import unittest

from app.core.fs364_outbox_transition import OutboxRecord, transition


def pending(**overrides):
    data = dict(event_id="event-147", revision=0, status="PENDING",
                attempt=0, tenant_id="tenant", idempotency_key="key",
                ticket_id=147, mode="DEMO")
    data.update(overrides)
    return OutboxRecord(**data)


class OutboxTransitionTests(unittest.TestCase):
    def test_claim_cas_and_replay(self):
        first = transition(pending(), expected_revision=0, action="CLAIM")
        self.assertEqual(first.status, "CLAIMED")
        self.assertEqual(first.record.attempt, 1)
        self.assertEqual(transition(first.record, expected_revision=0,
                                    action="ACK", revalidated=True).status, "DENIED")
        self.assertEqual(transition(first.record, expected_revision=1,
                                    action="CLAIM").status, "DENIED")

    def test_ack_requires_revalidation(self):
        claimed = transition(pending(), expected_revision=0,
                             action="CLAIM").record
        self.assertEqual(transition(claimed, expected_revision=1,
                                    action="ACK").status, "DENIED")
        ack = transition(claimed, expected_revision=1, action="ACK",
                         revalidated=True)
        self.assertEqual(ack.status, "ACKED")
        self.assertEqual(transition(ack.record, expected_revision=2,
                                    action="ACK", revalidated=True).status, "DENIED")

    def test_requeue_after_unknown_delivery_is_not_dispatch_permission(self):
        claimed = transition(pending(), expected_revision=0,
                             action="CLAIM").record
        retried = transition(claimed, expected_revision=1,
                             action="REQUEUE")
        self.assertEqual(retried.status, "REQUEUED")
        self.assertEqual(retried.record.attempt, 1)
        self.assertEqual(transition(retried.record, expected_revision=2,
                                    action="ACK", revalidated=True).status, "DENIED")

    def test_forbidden_mode_ticket_and_types(self):
        for record in (pending(mode="LIVE"), pending(ticket_id=146),
                       pending(ticket_id=True), pending(revision=True),
                       pending(idempotency_key="bad key")):
            with self.subTest(record=record):
                self.assertEqual(transition(record, expected_revision=0,
                                            action="CLAIM").status, "DENIED")

    def test_no_input_mutation(self):
        original = pending()
        transition(original, expected_revision=0, action="CLAIM")
        self.assertEqual(original, pending())


if __name__ == "__main__":
    unittest.main()
