"""Offline regression: conflicting ON CONFLICT receipt winners are never acknowledged."""
import pathlib
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_core_live_execute_guard import HTTPException, load_execute


class ReceiptDB:
    def __init__(self, winner):
        self.winner = winner
        self.queries = []
        self.receipt_reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.queries.append(query)
        return self

    def fetchone(self):
        query = self.queries[-1].lower().strip()
        if query.startswith("select workflow_id"):
            self.receipt_reads += 1
            if self.receipt_reads == 1:
                return None  # No receipt before Worker dispatch
            return None if self.winner is None else (self.winner,)
        return ("RUN-1", "DEMO", "scenario", 1, "CREATED")


class ConflictingReceiptWinnerTests(unittest.TestCase):
    def test_concurrent_foreign_or_missing_winner_fails_closed(self):
        for winner in ("RUN-OTHER", "", None):
            with self.subTest(winner=winner):
                connection = ReceiptDB(winner)
                requests = Mock()
                response = requests.post.return_value
                response.json.return_value = {
                    "run_id": "RUN-1", "workflow_id": "RUN-1"
                }
                execute = load_execute(lambda: connection, requests)
                with self.assertRaises(HTTPException) as caught:
                    execute("RUN-1", "Bearer offline-test")
                self.assertEqual(caught.exception.status_code, 409)
                requests.post.assert_called_once()
                self.assertEqual(connection.receipt_reads, 2)

    def test_matching_winner_returns_canonical_identity(self):
        connection = ReceiptDB("RUN-1")
        requests = Mock()
        requests.post.return_value.json.return_value = {
            "run_id": "RUN-1", "workflow_id": "RUN-1"
        }
        result = load_execute(lambda: connection, requests)(
            "RUN-1", "Bearer offline-test"
        )
        self.assertEqual(result["workflow_id"], "RUN-1")
        self.assertEqual(connection.receipt_reads, 2)


if __name__ == "__main__":
    unittest.main()
