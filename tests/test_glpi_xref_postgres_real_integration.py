"""Real PostgreSQL GLPI xref nonce barrier; disposable CI DB only."""
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_xref_postgres_nonce import make_postgres_nonce_consumer


@unittest.skipUnless(os.environ.get("AIOPS_GLPI_NONCE_REAL_PG_CI") == "1",
                     "requires explicitly enabled disposable PostgreSQL CI")
class RealPostgresNonceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.dsn = os.environ["DATABASE_URL"]
        with psycopg.connect(cls.dsn) as connection:
            connection.execute((Path("db/migrations") /
                                "011_glpi_xref_nonce_replay_barrier.sql").read_text())

    def setUp(self):
        self.nonce = uuid4().hex
        self.consume = make_postgres_nonce_consumer(
            lambda: self.psycopg.connect(self.dsn))
        self.args = {"tenant_id": "ci-tenant-a", "nonce": self.nonce,
                     "expires_at": 2_100_000_000}

    def test_nonce_is_durable_across_connections_and_tenant_scoped(self):
        self.assertTrue(self.consume(**self.args))
        self.assertFalse(self.consume(**self.args))
        self.assertTrue(self.consume(**{**self.args, "tenant_id": "ci-tenant-b"}))
        self.assertFalse(self.consume(**self.args))

    def test_concurrent_insert_has_exactly_one_winner(self):
        workers = 8
        barrier = Barrier(workers)
        def attempt(_):
            barrier.wait(timeout=10)
            return self.consume(**self.args)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(attempt, range(workers)))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), workers - 1)

    def test_expired_nonce_is_not_pruned_or_reusable(self):
        expired = {**self.args, "expires_at": 1}
        self.assertTrue(self.consume(**expired))
        self.assertFalse(self.consume(**self.args))
        with self.psycopg.connect(self.dsn) as connection:
            row = connection.execute(
                "SELECT count(*) FROM aiops.glpi_xref_consumed_nonces "
                "WHERE tenant_id=%s AND nonce=%s",
                (self.args["tenant_id"], self.nonce),
            ).fetchone()
        self.assertEqual(row, (1,))

    def test_closed_database_connection_fails_closed(self):
        def closed_connect():
            connection = self.psycopg.connect(self.dsn)
            connection.close()
            return connection
        self.assertFalse(make_postgres_nonce_consumer(closed_connect)(**self.args))


if __name__ == "__main__":
    unittest.main()
