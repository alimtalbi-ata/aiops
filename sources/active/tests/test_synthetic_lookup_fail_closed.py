"""Core must not start Temporal when lookup is unverified."""
import importlib
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import requests
from fastapi import HTTPException

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "test-only-internal-token")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@127.0.0.1:5432/test",
)

core = importlib.import_module("core.main")


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDB:
    def execute(self, sql, params=None):
        if "from aiops.runs" in sql:
            return Result((
                "RUN-TEST",
                "DEMO",
                "SCN-GOLDEN-PAYMENT-P1",
                1,
                "CREATED",
            ))
        if "from aiops.execution_receipts" in sql:
            return Result(None)
        raise AssertionError(sql)


class FakeResponse:
    def __init__(self, status, detail):
        self.status_code = status
        self.detail = detail

    def json(self):
        return {"detail": self.detail}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                "upstream failure",
                response=self,
            )


class FailClosedTests(unittest.TestCase):
    def execute_with_lookup(self, response=None, error=None):
        @contextmanager
        def fake_db():
            yield FakeDB()

        with (
            patch.object(core, "db", fake_db),
            patch.object(core, "auth", return_value=None),
            patch.object(core.requests, "get") as get,
            patch.object(core.requests, "post") as post,
        ):
            if error:
                get.side_effect = error
            else:
                get.return_value = response

            with self.assertRaises(HTTPException) as caught:
                core.execute(
                    "RUN-TEST",
                    authorization="Bearer test",
                )

            post.assert_not_called()
            return caught.exception.status_code

    def test_generic_404_does_not_start(self):
        status = self.execute_with_lookup(
            FakeResponse(404, "Not Found")
        )
        self.assertEqual(status, 503)

    def test_temporal_unavailable_does_not_start(self):
        status = self.execute_with_lookup(
            FakeResponse(503, "temporal_lookup_unavailable")
        )
        self.assertEqual(status, 503)

    def test_lookup_timeout_does_not_start(self):
        status = self.execute_with_lookup(
            error=requests.Timeout("lookup timed out")
        )
        self.assertEqual(status, 503)


if __name__ == "__main__":
    unittest.main()
