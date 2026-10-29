"""Behavioral tests for atomic synthetic launch without PostgreSQL."""
import importlib
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault(
    "AIOPS_INTERNAL_TOKEN",
    "test-only-internal-token",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@127.0.0.1:5432/test",
)

from fastapi import HTTPException

core = importlib.import_module("core.main")


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDB:
    def __init__(self, scenario=(True,), run=None, incident=None):
        self.scenario = scenario
        self.run = run
        self.incident = incident
        self.writes = []
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)
        normalized = " ".join(sql.lower().split())

        if "pg_advisory_xact_lock" in normalized:
            return Result((None,))
        if "select synthetic from aiops.scenarios" in normalized:
            return Result(self.scenario)
        if "select run_id,mode,scenario_id,incident_id,status from aiops.runs" in normalized:
            return Result(self.run)
        if "select incident_id from aiops.incidents" in normalized:
            return Result(self.incident)
        if normalized.startswith("insert into"):
            self.writes.append((sql, params))
            return Result()

        raise AssertionError(f"Unexpected SQL: {sql}")


class LaunchBehaviorTests(unittest.TestCase):
    def launch(self, fake, key="test-key", mode="DEMO"):
        @contextmanager
        def fake_db():
            yield fake

        payload = core.SyntheticLaunchIn(
            scenario_id="SCN-GOLDEN-PAYMENT-P1",
            mode=mode,
            idempotency_key=key,
        )

        with (
            patch.object(core, "db", fake_db),
            patch.object(core, "auth", return_value=None),
            patch.object(core, "new", return_value="RUN-TEST"),
            patch.object(core, "append_event") as event,
        ):
            result = core.create_synthetic_launch(
                payload,
                authorization="Bearer test",
            )
            return result, event.call_count

    def test_nominal_creates_incident_run_and_stages(self):
        fake = FakeDB()
        result, event_count = self.launch(fake)

        self.assertEqual(result["run_id"], "RUN-TEST")
        self.assertFalse(result["idempotent"])
        self.assertEqual(event_count, 1)

        sql = " ".join(query.lower() for query, _ in fake.writes)
        self.assertIn("insert into aiops.incidents", sql)
        self.assertIn("insert into aiops.runs", sql)
        self.assertIn("insert into aiops.run_stage_state", sql)

    def test_same_key_returns_existing_run_without_writes(self):
        fake = FakeDB(
            run=(
                "RUN-EXISTING",
                "DEMO",
                "SCN-GOLDEN-PAYMENT-P1",
                "INC-test-key",
                "RUNNING",
            )
        )
        result, event_count = self.launch(fake)

        self.assertEqual(result["run_id"], "RUN-EXISTING")
        self.assertTrue(result["idempotent"])
        self.assertEqual(fake.writes, [])
        self.assertEqual(event_count, 0)

    def test_conflicting_key_is_rejected(self):
        fake = FakeDB(
            run=(
                "RUN-EXISTING",
                "REPLAY",
                "SCN-GOLDEN-PAYMENT-P1",
                "INC-test-key",
                "RUNNING",
            )
        )

        with self.assertRaises(HTTPException) as caught:
            self.launch(fake)

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(fake.writes, [])

    def test_non_synthetic_scenario_is_rejected(self):
        fake = FakeDB(scenario=(False,))

        with self.assertRaises(HTTPException) as caught:
            self.launch(fake)

        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(fake.writes, [])


if __name__ == "__main__":
    unittest.main()
