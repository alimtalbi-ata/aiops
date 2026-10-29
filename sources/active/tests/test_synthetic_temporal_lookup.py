"""Worker Temporal lookup: found, absent, unavailable, unauthorized."""
import asyncio
import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from temporalio.service import RPCError, RPCStatusCode

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "test-only-internal-token")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@127.0.0.1:5432/test",
)

worker = importlib.import_module("worker.main")


class FakeHandle:
    def __init__(self, error=None):
        self.error = error
        self.describe_calls = 0

    async def describe(self):
        self.describe_calls += 1
        if self.error:
            raise self.error
        return object()


class FakeClient:
    def __init__(self, handle):
        self.handle = handle
        self.lookups = []

    def get_workflow_handle(self, rid):
        self.lookups.append(rid)
        return self.handle

    async def start_workflow(self, *args, **kwargs):
        raise AssertionError("Lookup must never start a workflow")


class LookupTests(unittest.TestCase):
    def call_lookup(self, client):
        with patch.object(
            worker.Client,
            "connect",
            new=AsyncMock(return_value=client),
        ):
            return asyncio.run(
                worker.lookup_execution(
                    "RUN-TEST",
                    authorization=f"Bearer {worker.ADMIN}",
                )
            )

    def test_existing_workflow(self):
        handle = FakeHandle()
        client = FakeClient(handle)

        result = self.call_lookup(client)

        self.assertEqual(result["workflow_id"], "RUN-TEST")
        self.assertTrue(result["idempotent"])
        self.assertEqual(client.lookups, ["RUN-TEST"])
        self.assertEqual(handle.describe_calls, 1)

    def test_missing_workflow(self):
        error = RPCError(
            "workflow not found",
            RPCStatusCode.NOT_FOUND,
            b"",
        )
        client = FakeClient(FakeHandle(error))

        with self.assertRaises(HTTPException) as caught:
            self.call_lookup(client)

        self.assertEqual(caught.exception.status_code, 404)

    def test_temporal_unavailable(self):
        client = FakeClient(
            FakeHandle(ConnectionError("Temporal unavailable"))
        )

        with self.assertRaises(HTTPException) as caught:
            self.call_lookup(client)

        self.assertEqual(caught.exception.status_code, 503)

    def test_unauthorized(self):
        with patch.object(
            worker.Client,
            "connect",
            new=AsyncMock(),
        ) as connect:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(
                    worker.lookup_execution(
                        "RUN-TEST",
                        authorization="Bearer invalid",
                    )
                )

        self.assertEqual(caught.exception.status_code, 401)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
