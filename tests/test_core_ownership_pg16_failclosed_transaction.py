"""#233 regression: no success if PG16 commit fails or its outcome is unknown.

These are DB-API seam tests, NOT a PG16 concurrency/restore qualification.
"""
import unittest
from core.ownership_pg16_ledger import LedgerUnavailable, consume_once_pg16


class Cursor:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, statement, params):
        assert "ON CONFLICT (issuer, jti) DO NOTHING" in statement
        self.conn.params = params
    def fetchone(self):
        if self.conn.fetch_error:
            raise ConnectionError("result unavailable")
        return ("issuer",)


class Connection:
    autocommit = False
    def __init__(self, commit_error=False, rollback_error=False, fetch_error=False):
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.fetch_error = fetch_error
        self.commits = 0
        self.rollbacks = 0
    def cursor(self):
        return Cursor(self)
    def commit(self):
        self.commits += 1
        if self.commit_error:
            raise ConnectionError("commit outcome unknown")
    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error:
            raise ConnectionError("rollback unavailable")


class FailClosedTransactionTests(unittest.TestCase):
    def test_commit_error_never_returns_allow(self):
        conn = Connection(commit_error=True)
        with self.assertRaises(LedgerUnavailable):
            consume_once_pg16(conn, "oidc", "jti", 1800000120)
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 1)

    def test_commit_and_rollback_error_still_denies(self):
        conn = Connection(commit_error=True, rollback_error=True)
        with self.assertRaises(LedgerUnavailable):
            consume_once_pg16(conn, "oidc", "jti", 1800000120)
        self.assertEqual(conn.rollbacks, 1)

    def test_unknown_insert_result_rolls_back(self):
        conn = Connection(fetch_error=True)
        with self.assertRaises(LedgerUnavailable):
            consume_once_pg16(conn, "oidc", "jti", 1800000120)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
