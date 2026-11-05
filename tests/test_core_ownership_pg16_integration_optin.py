"""Opt-in disposable PG16 concurrency/reconnect qualification for Core #233.

Never runs against a production database by default. Requires a dedicated
throwaway database and two explicit environment variables. No LIVE writes.
Run: CORE_OWNERSHIP_ALLOW_EPHEMERAL_PG16=YES
     CORE_OWNERSHIP_TEST_DSN='postgresql://.../throwaway_db'
     PYTHONPATH=app python -m unittest tests/test_core_ownership_pg16_integration_optin.py
"""
import concurrent.futures
import os
import unittest
import uuid

from core.ownership_pg16_ledger import consume_once_pg16


@unittest.skipUnless(
    os.getenv("CORE_OWNERSHIP_ALLOW_EPHEMERAL_PG16") == "YES"
    and os.getenv("CORE_OWNERSHIP_TEST_DSN"),
    "explicit disposable PG16 opt-in required",
)
class DisposablePG16LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest("psycopg required for PG16 integration") from exc
        cls.psycopg = psycopg
        cls.dsn = os.environ["CORE_OWNERSHIP_TEST_DSN"]
        cls.schema = "ownership_test_" + uuid.uuid4().hex
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

    @classmethod
    def consume(cls, issuer, jti):
        with cls.psycopg.connect(cls.dsn, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{cls.schema}"')
            connection.commit()
            return consume_once_pg16(connection, issuer, jti, 1800000120)

    def test_concurrent_exactly_one_winner_and_reconnect_replay(self):
        key = uuid.uuid4().hex
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.consume("issuer", key), range(16)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 15)
        self.assertIs(self.consume("issuer", key), False)
        self.assertIs(self.consume("other-issuer", key), True)

    def test_reconnect_keeps_consumed_key(self):
        key = uuid.uuid4().hex
        self.assertIs(self.consume("issuer", key), True)
        self.assertIs(self.consume("issuer", key), False)


if __name__ == "__main__":
    unittest.main()
