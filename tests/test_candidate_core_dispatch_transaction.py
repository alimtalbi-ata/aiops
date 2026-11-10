"""Execute transaction lifetime; offline doubles, not PostgreSQL concurrency proof."""
import unittest
from unittest.mock import Mock
from requests.exceptions import Timeout
from test_candidate_core_execute import HTTPException, load_execute
from test_candidate_core_receipt_winner import ReceiptDB


class TransactionDB(ReceiptDB):
    def __init__(self):
        super().__init__('RUN-1')
        self.active = False
        self.exits = []

    def __enter__(self):
        self.active = True
        return self

    def __exit__(self, exc_type, *args):
        self.exits.append(exc_type)
        self.active = False
        return False


class DispatchTransactionTests(unittest.TestCase):
    def test_dispatch_and_receipt_share_locked_transaction(self):
        connection = TransactionDB()
        requests = Mock()
        response = Mock()
        response.json.return_value = {'run_id': 'RUN-1', 'workflow_id': 'RUN-1'}

        def dispatch(*args, **kwargs):
            self.assertTrue(connection.active, 'Run lock released before Worker start')
            self.assertEqual(connection.exits, [])
            return response

        requests.post.side_effect = dispatch
        result = load_execute(lambda: connection, requests)('RUN-1', 'Bearer offline-test')
        self.assertEqual(result['workflow_id'], 'RUN-1')
        self.assertEqual(connection.receipt_reads, 2)
        self.assertEqual(connection.exits, [None])
        self.assertFalse(connection.active)

    def test_timeout_exits_with_error_without_receipt_write(self):
        connection = TransactionDB()
        requests = Mock()
        requests.post.side_effect = Timeout('ambiguous start')
        with self.assertRaises(HTTPException) as caught:
            load_execute(lambda: connection, requests)('RUN-1', 'Bearer offline-test')
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(connection.exits, [HTTPException])
        self.assertFalse(connection.active)
        self.assertFalse(any('insert into' in q.lower() for q in connection.queries))
