"""Opt-in PG16 transaction-abort and reconnect regression for Core #233.

Requires the same explicitly disposable PG16 environment as the concurrency
suite. No production database is accessed by default.
"""
import os
import unittest
import uuid

from core.ownership_pg16_ledger import LedgerUnavailable, consume_once_pg16


@unittest.skipUnless(
    os.getenv("CORE_OWNERSHIP_ALLOW_EPHEMERAL_PG16") == "YES"
    and os.getenv("CORE_OWNERSHIP_TEST_DSN"),
    "explicit disposable PG16 opt-in required",
)
class DisposablePG16AbortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest("psycopg required") from exc
        cls.psycopg = psycopg
        cls.dsn = os.environ["CORE_OWNERSHIP_TEST_DSN"]
        cls.schema = "ownership_abort_" + uuid.uuid4().hex
        cls.admin = psycopg.connect(cls.dsn, autocommit=True)
        try:
            version = int(cls.admin.execute("SHOW server_version_num").fetchone()[0])
            if version // 10000 != 16:
                raise unittest.SkipTest("requires PostgreSQL 16")
            cls.admin.execute(f'CREATE SCHEMA "{cls.schema}"')
            cls.admin.execute(
                f'CREATE TABLE "{cls.schema}".core_ownership_replay_ledger ('
                'issuer text NOT NULL, jti text NOT NULL, '
                'expires_at timestamptz NOT NULL, '
                'consumed_at timestamptz NOT NULL DEFAULT transaction_timestamp(), '
                'PRIMARY KEY (issuer, jti))'
            )
        except BaseException:
            cls.admin.close()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.admin.execute(f'DROP SCHEMA IF EXISTS "{cls.schema}" CASCADE')
        finally:
            cls.admin.close()

    def connect(self):
        connection = self.psycopg.connect(self.dsn, autocommit=False)
        connection.execute(f'SET search_path TO "{self.schema}"')
        connection.commit()
        return connection

    def test_aborted_transaction_never_returns_success_and_reconnect_recovers(self):
        issuer, jti = "issuer", uuid.uuid4().hex
        with self.connect() as connection:
            # Leave transaction in an aborted state before consumption.
            with self.assertRaises(self.psycopg.errors.DivisionByZero):
                connection.execute("SELECT 1 / 0")
            with self.assertRaises(LedgerUnavailable):
                consume_once_pg16(connection, issuer, jti, 1800000120)
        with self.connect() as connection:
            self.assertIs(consume_once_pg16(connection, issuer, jti, 1800000120), True)
        with self.connect() as connection:
            self.assertIs(consume_once_pg16(connection, issuer, jti, 1800000120), False)


if __name__ == "__main__":
    unittest.main()
