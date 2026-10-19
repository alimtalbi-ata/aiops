import unittest

from shared.idempotency import IdempotencyConflict, resolve_receipt


class IdempotencyReceiptTests(unittest.TestCase):
    def test_missing_receipt_returns_none(self):
        self.assertIsNone(resolve_receipt(None, "RUN-1", "START"))

    def test_exact_same_operation_replays_response(self):
        response = {"run_id": "RUN-1", "status": "RUNNING", "version": 2}
        self.assertEqual(resolve_receipt(("RUN-1", "START", response), "RUN-1", "START"), response)

    def test_key_reused_for_different_run_is_rejected(self):
        with self.assertRaisesRegex(IdempotencyConflict, "different run or command"):
            resolve_receipt(("RUN-1", "START", {"run_id": "RUN-1"}), "RUN-2", "START")

    def test_key_reused_for_different_command_is_rejected(self):
        with self.assertRaisesRegex(IdempotencyConflict, "different run or command"):
            resolve_receipt(("RUN-1", "START", {"run_id": "RUN-1"}), "RUN-1", "CANCEL")

    def test_stored_response_is_not_rewritten(self):
        response = {"status": "BLOCKED", "version": 9, "audit": ["event-a"]}
        self.assertIs(resolve_receipt(("RUN-1", "WAIT", response), "RUN-1", "WAIT"), response)


if __name__ == "__main__":
    unittest.main()
