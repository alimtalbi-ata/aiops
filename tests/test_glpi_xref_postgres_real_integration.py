"""Real PostgreSQL replay barrier integration, isolated GitHub Actions DB only.

No Debian host, GLPI server, production credential or production migration.
Requires DATABASE_URL pointing to disposable CI PostgreSQL and psycopg 3.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_xref_postgres_nonce import make_postgres_nonce_consumer


@unittest.skipUnless(os.environ.get("AIOPS_GLPI_NONCE_REAL_PG_CI") == "1",
                     "requires explicitly enabled disposable PostgreSQL CI")
class RealPostgresNonceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.url = os.environ["DATABASE_URL"]
        with psycopg.connect(cls.url) as connection:
            connection.execute("CREATE SCHEMA IF NOT EXISTS aiops")
            connection.execute(Path(
                "docs/sql/glpi_xref_nonce_replay_barrier.sql").read_text())

    def setUp(self):
        import uuid
        self.nonce = uuid.uuid4().hex
        self.consumer = make_postgres_nonce_consumer(
            lambda: self.psycopg.connect(self.url))
        self.args = dict(tenant_id="ci-tenant-a", nonce=self.nonce,
                         expires_at=1900000000)

    def test_unique_nonce_survives_new_connections(self):
        self.assertTrue(self.consumer(**self.args))
        self.assertFalse(self.consumer(**self.args))
        with self.psycopg.connect(self.url) as connection:
            row = connection.execute(
                "SELECT count(*) FROM aiops.glpi_xref_consumed_nonces "
                "WHERE tenant_id=%s AND nonce=%s",
                ("ci-tenant-a", self.nonce)).fetchone()
        self.assertEqual(row, (1,))

    def test_tenant_scoping_in_real_unique_index(self):
        self.assertTrue(self.consumer(**self.args))
        self.assertTrue(self.consumer(**{**self.args, "tenant_id": "ci-tenant-b"}))
        self.assertFalse(self.consumer(**self.args))

    def test_database_statement_failure_is_denied(self):
        # The real failure path is exercised using a closed DB connection.
        def closed_connect():
            connection = self.psycopg.connect(self.url)
            connection.close()
            return connection
        self.assertFalse(make_postgres_nonce_consumer(closed_connect)(
            **self.args))


if __name__ == "__main__":
    unittest.main()
