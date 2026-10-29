"""Simulate lost Temporal response and idempotent recovery."""

import importlib
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import requests
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

RID = "RUN-TIMEOUT-TEST"


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDatabase:
    def __init__(self):
        self.status = "CREATED"
        self.receipt = None
        self.receipt_writes = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())

        if "from aiops.runs" in normalized:
            return Result((
                RID,
                "DEMO",
                "SCN-GOLDEN-PAYMENT-P1",
                1,
                self.status,
            ))

        if (
            normalized.startswith("select workflow_id")
            and "from aiops.execution_receipts" in normalized
        ):
            return Result(
                (self.receipt,) if self.receipt else None
            )

        if normalized.startswith(
            "insert into aiops.execution_receipts"
        ):
            self.receipt_writes += 1
            if self.receipt is None:
                self.receipt = params[1]
            return Result(None)

        raise AssertionError(f"Unexpected SQL: {sql}")


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}",
                response=self,
            )

    def json(self):
        return self.payload


class TemporalStub:
    def __init__(self):
        self.started = set()
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        if self.started:
            return FakeResponse({
                "run_id": RID,
                "workflow_id": RID,
                "executor": "temporal",
                "idempotent": True,
            })
        return FakeResponse(
            {"detail": "workflow_not_found"},
            status_code=404,
        )

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls += 1
        rid = json["run_id"]

        if rid not in self.started:
            self.started.add(rid)
            raise requests.Timeout(
                "Simulated lost response after Temporal accepted workflow"
            )

        return FakeResponse({
            "run_id": rid,
            "workflow_id": rid,
            "executor": "temporal",
            "idempotent": True,
        })


class TemporalTimeoutTests(unittest.TestCase):
    def test_timeout_then_recovery_then_receipt_reuse(self):
        database = FakeDatabase()
        temporal = TemporalStub()

        @contextmanager
        def fake_db():
            yield database

        with (
            patch.object(core, "db", fake_db),
            patch.object(core, "auth", return_value=None),
            patch.object(core.requests, "post", temporal.post),
            patch.object(core.requests, "get", temporal.get),
        ):
            # First call: Temporal accepts, but its response is lost.
            with self.assertRaises(HTTPException) as caught:
                core.execute(
                    RID,
                    authorization="Bearer test",
                )

            self.assertEqual(caught.exception.status_code, 503)
            self.assertEqual(temporal.calls, 1)
            self.assertEqual(temporal.started, {RID})
            self.assertIsNone(database.receipt)

            # Retry: same run_id, Temporal returns existing workflow.
            recovered = core.execute(
                RID,
                authorization="Bearer test",
            )

            self.assertEqual(recovered["workflow_id"], RID)
            self.assertTrue(recovered["idempotent"])
            self.assertEqual(temporal.calls, 1)
            self.assertEqual(database.receipt, RID)
            self.assertEqual(database.receipt_writes, 1)

            # Subsequent retry: Core uses PostgreSQL receipt.
            database.status = "RUNNING"

            repeated = core.execute(
                RID,
                authorization="Bearer test",
            )

            self.assertEqual(repeated["workflow_id"], RID)
            self.assertTrue(repeated["idempotent"])
            self.assertEqual(temporal.calls, 1)
            self.assertEqual(database.receipt_writes, 1)


if __name__ == "__main__":
    unittest.main()
