"""Pure negative contract checks: invalid resume claims never mutate SQLite.

Run: python -m unittest -v tests.test_fs364_claim_input_validation
No GLPI, Temporal, filesystem or LIVE calls.
"""
import sqlite3
import unittest
from app.core.fs364_resume_claim import claim_resume


class ClaimInputValidationTests(unittest.TestCase):
    def test_invalid_version_or_request_id_does_not_create_schema(self):
        bad = [
            (None, "req-1"), ("", "req-1"), (" v1", "req-1"),
            ("v1 ", "req-1"), (123, "req-1"), ("v1", None),
            ("v1", ""), ("v1", " req-1"), ("v1", "req-1 "),
            ("v1", 123),
        ]
        for version, request_id in bad:
            with self.subTest(version=version, request_id=request_id):
                conn = sqlite3.connect(":memory:")
                try:
                    self.assertFalse(claim_resume(
                        conn, None, None, expected_tenant_id="tenant-A",
                        state_version=version, request_id=request_id
                    ))
                    self.assertFalse(conn.in_transaction)
                    self.assertEqual(conn.execute(
                        "SELECT name FROM sqlite_master WHERE name='fs364_resume_claims'"
                    ).fetchall(), [])
                finally:
                    conn.close()

    def test_invalid_claim_does_not_change_preexisting_committed_data(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
            conn.execute("INSERT INTO sentinel VALUES ('unchanged')")
            conn.commit()
            self.assertFalse(claim_resume(
                conn, None, None, expected_tenant_id="tenant-A",
                state_version="v1", request_id=" "
            ))
            self.assertEqual(conn.execute("SELECT value FROM sentinel").fetchall(),
                             [("unchanged",)])
            self.assertFalse(conn.in_transaction)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
