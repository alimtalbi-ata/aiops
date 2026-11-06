"""Regression: an FS364 claim must not destroy a caller-owned transaction.

Run: python -m unittest -v tests.test_fs364_claim_transaction_ownership
No GLPI, Temporal, filesystem, or LIVE calls.
"""
import sqlite3
import unittest
from app.core.fs364_resume_claim import claim_resume


class ClaimTransactionOwnershipTests(unittest.TestCase):
    def test_nested_claim_preserves_uncommitted_caller_write(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE caller_work (id INTEGER PRIMARY KEY, note TEXT)")
            conn.commit()
            conn.execute("BEGIN")
            conn.execute("INSERT INTO caller_work(note) VALUES ('preserve')")
            # Must reject before inspecting the invalid snapshot/ticket.
            self.assertFalse(claim_resume(
                conn, None, None, expected_tenant_id="tenant-A",
                state_version="v1", request_id="req-1"))
            self.assertTrue(conn.in_transaction)
            self.assertEqual(conn.execute("SELECT note FROM caller_work").fetchall(),
                             [("preserve",)])
            conn.commit()
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM caller_work").fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT name FROM sqlite_master WHERE name='fs364_resume_claims'"
            ).fetchall(), [])
        finally:
            conn.close()

    def test_invalid_request_does_not_open_or_close_caller_transaction(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("BEGIN")
            self.assertFalse(claim_resume(
                conn, None, None, expected_tenant_id="tenant-A",
                state_version=" ", request_id="req-1"))
            self.assertTrue(conn.in_transaction)
            conn.rollback()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
