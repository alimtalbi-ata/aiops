"""Non-regression: an existing Temporal receipt must win over run status."""
import importlib
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

os.environ.setdefault(
    "AIOPS_INTERNAL_TOKEN",
    "test-only-internal-token",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@127.0.0.1:5432/test",
)

core = importlib.import_module("core.main")


class FakeConnection:
    def __init__(self, status, receipt):
        self.status = status
        self.receipt = receipt
        self.queries = []

    def execute(self, sql, params):
        self.queries.append(sql)
        if "from aiops.runs" in sql:
            return FakeResult(
                ("RUN-TEST", "DEMO", "SCN-GOLDEN-PAYMENT-P1", 1, self.status)
            )
        if "from aiops.execution_receipts" in sql:
            return FakeResult(
                (self.receipt,) if self.receipt else None
            )
        raise AssertionError(f"Unexpected SQL: {sql}")


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class ExecuteReceiptTests(unittest.TestCase):
    def run_execute(self, status, receipt):
        conn = FakeConnection(status, receipt)

        @contextmanager
        def fake_db():
            yield conn

        with (
            patch.object(core, "db", fake_db),
            patch.object(core, "auth", return_value=None),
            patch.object(core.requests, "post") as post,
            patch.object(core.requests, "get") as get,
        ):
            if receipt is None:
                response = get.return_value
                response.status_code = 404
                response.json.return_value = {
                    "detail": "workflow_not_found"
                }
                with self.assertRaises(HTTPException) as caught:
                    core.execute("RUN-TEST", authorization="Bearer test")
                self.assertEqual(caught.exception.status_code, 409)
                result = None
            else:
                result = core.execute(
                    "RUN-TEST",
                    authorization="Bearer test",
                )

            post.assert_not_called()

        return result, conn

    def test_running_run_returns_existing_receipt(self):
        result, conn = self.run_execute("RUNNING", "RUN-TEST")
        self.assertEqual(result["workflow_id"], "RUN-TEST")
        self.assertTrue(result["idempotent"])
        self.assertEqual(len(conn.queries), 2)

    def test_completed_run_returns_existing_receipt(self):
        result, _ = self.run_execute("COMPLETED", "RUN-TEST")
        self.assertTrue(result["idempotent"])

    def test_running_without_receipt_is_rejected(self):
        result, _ = self.run_execute("RUNNING", None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
