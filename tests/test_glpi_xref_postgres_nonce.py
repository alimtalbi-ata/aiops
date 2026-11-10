"""Offline DB-API contract tests for PostgreSQL replay protection."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_xref_postgres_nonce import make_postgres_nonce_consumer


class Cursor:
    def __init__(self, db):
        self.db = db
        self.inserted = None
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params):
        assert "ON CONFLICT (tenant_id, nonce) DO NOTHING" in sql
        assert "RETURNING nonce" in sql
        key = params[:2]
        if key in self.db.seen:
            self.inserted = None
        else:
            self.db.seen.add(key)
            self.inserted = key[1]
    def fetchone(self):
        return (self.inserted,) if self.inserted else None


class Connection:
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return Cursor(self.db)
    def close(self):
        self.db.closed += 1


class DB:
    def __init__(self):
        self.seen = set()
        self.connections = 0
        self.closed = 0
    def connect(self):
        self.connections += 1
        return Connection(self)


class NonceBarrierTests(unittest.TestCase):
    def setUp(self):
        self.db = DB()
        self.consume = make_postgres_nonce_consumer(self.db.connect)
        self.args = dict(tenant_id="tenant-a", nonce="nonce123456789012",
                         expires_at=1900000000)

    def test_first_insert_allowed_second_rejected(self):
        self.assertTrue(self.consume(**self.args))
        self.assertFalse(self.consume(**self.args))
        self.assertEqual(self.db.connections, 2)
        self.assertEqual(self.db.closed, 2)

    def test_different_tenant_is_distinct_namespace(self):
        self.assertTrue(self.consume(**self.args))
        self.assertTrue(self.consume(**{**self.args, "tenant_id": "tenant-b"}))

    def test_invalid_inputs_never_connect(self):
        for changes in ({"nonce": "bad"}, {"tenant_id": ""},
                        {"expires_at": True}, {"expires_at": -1}):
            self.assertFalse(self.consume(**{**self.args, **changes}))
        self.assertEqual(self.db.connections, 0)

    def test_database_error_denies(self):
        def broken():
            raise ConnectionError("offline")
        self.assertFalse(make_postgres_nonce_consumer(broken)(**self.args))

    def test_commit_failure_never_reports_nonce_consumed(self):
        class CommitFailureConnection(Connection):
            def __exit__(self, *args):
                raise RuntimeError("commit failed")
        self.assertFalse(make_postgres_nonce_consumer(
            lambda: CommitFailureConnection(self.db))(**self.args))
        self.assertEqual(self.db.closed, 1)

    def test_cursor_error_never_reports_nonce_consumed(self):
        class BrokenCursor(Cursor):
            def execute(self, sql, params):
                raise RuntimeError("statement failed")
        class BrokenConnection(Connection):
            def cursor(self):
                return BrokenCursor(self.db)
        self.assertFalse(make_postgres_nonce_consumer(
            lambda: BrokenConnection(self.db))(**self.args))
        self.assertEqual(self.db.closed, 1)

    def test_missing_connection_factory_rejected(self):
        with self.assertRaises(ValueError):
            make_postgres_nonce_consumer(None)


if __name__ == "__main__":
    unittest.main()
