"""DB-API contract tests; PG16 integration/concurrency/restore remain separate gates."""
import unittest
from core.ownership_pg16_ledger import consume_once_pg16, LedgerUnavailable


class Cursor:
    def __init__(self, connection):
        self.connection = connection
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, query, params):
        assert "ON CONFLICT (issuer, jti) DO NOTHING" in query
        assert params[0] and params[1]
        self.connection.params = params
    def fetchone(self):
        return ("issuer",) if self.connection.inserted else None


class Connection:
    autocommit = False
    def __init__(self, inserted=True, fail=False):
        self.inserted = inserted
        self.fail = fail
        self.commits = 0
        self.rollbacks = 0
    def cursor(self):
        if self.fail:
            raise ConnectionError("PG16 down")
        return Cursor(self)
    def commit(self):
        self.commits += 1
    def rollback(self):
        self.rollbacks += 1


class ReplayLedgerContractTests(unittest.TestCase):
    def test_first_insert_committed(self):
        c = Connection()
        self.assertIs(consume_once_pg16(c, "issuer", "jti", 1800000120), True)
        self.assertEqual(c.commits, 1)
        self.assertEqual(c.params, ("issuer", "jti", 1800000120))

    def test_conflict_is_denied_and_committed(self):
        c = Connection(inserted=False)
        self.assertIs(consume_once_pg16(c, "issuer", "jti", 1800000120), False)
        self.assertEqual(c.commits, 1)

    def test_failure_rolls_back_and_denies(self):
        c = Connection(fail=True)
        with self.assertRaises(LedgerUnavailable):
            consume_once_pg16(c, "issuer", "jti", 1800000120)
        self.assertEqual(c.rollbacks, 1)
        self.assertEqual(c.commits, 0)

    def test_autocommit_and_bad_input_denied(self):
        c = Connection()
        c.autocommit = True
        with self.assertRaises(LedgerUnavailable):
            consume_once_pg16(c, "issuer", "jti", 1800000120)
        c.autocommit = False
        for issuer, jti, exp in [("", "jti", 10), ("issuer", "", 10), ("issuer", "jti", True)]:
            with self.assertRaises(LedgerUnavailable):
                consume_once_pg16(c, issuer, jti, exp)


if __name__ == "__main__":
    unittest.main()
