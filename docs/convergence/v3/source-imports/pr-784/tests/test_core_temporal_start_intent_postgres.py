"""Disposable PostgreSQL qualification for immutable Core start intent.

Run ONLY with AIOPS_START_INTENT_REAL_PG_CI=1 and DATABASE_URL pointing to
an isolated disposable CI database. Never run against production.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AIOPS_START_INTENT_REAL_PG_CI") != "1",
    reason="requires explicitly enabled disposable PostgreSQL CI",
)

MIGRATION = Path(__file__).resolve().parents[1] / "db/migrations/013_execution_start_intents.sql"


@pytest.fixture(scope="module")
def database_url():
    import psycopg
    dsn = os.environ["DATABASE_URL"]
    # Require an explicit disposable environment marker, never infer from DSN.
    assert os.environ.get("AIOPS_DISPOSABLE_DATABASE") == "1"
    with psycopg.connect(dsn) as conn:
        conn.execute(MIGRATION.read_text())
        # Migration must be idempotent.
        conn.execute(MIGRATION.read_text())
    return dsn


@pytest.fixture
def run_id(database_url):
    import psycopg
    rid = "RUN-CI-" + uuid4().hex
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
            "VALUES (%s,%s,%s,%s,%s)",
            (rid, "DEMO", "ci-scenario", "CREATED", rid),
        )
    return rid


def _claim(dsn, rid, barrier=None):
    import psycopg
    if barrier is not None:
        barrier.wait(timeout=20)
    with psycopg.connect(dsn) as conn:
        return conn.execute(
            "INSERT INTO aiops.execution_start_intents "
            "(run_id,mode,scenario_id,start_version) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT(run_id) DO NOTHING RETURNING run_id",
            (rid, "DEMO", "ci-scenario", 0),
        ).fetchone() is not None


def test_duplicate_intent_survives_new_connections(database_url, run_id):
    assert _claim(database_url, run_id)
    assert not _claim(database_url, run_id)


def test_concurrent_start_claim_has_exactly_one_winner(database_url, run_id):
    workers = 6
    barrier = Barrier(workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda _: _claim(database_url, run_id, barrier), range(workers)
        ))
    assert results.count(True) == 1
    assert results.count(False) == workers - 1


def test_mutation_is_denied_by_database(database_url, run_id):
    import psycopg
    assert _claim(database_url, run_id)
    with pytest.raises(psycopg.Error):
        with psycopg.connect(database_url) as conn:
            conn.execute(
                "UPDATE aiops.execution_start_intents SET start_version=9 "
                "WHERE run_id=%s", (run_id,)
            )
    with pytest.raises(psycopg.Error):
        with psycopg.connect(database_url) as conn:
            conn.execute(
                "DELETE FROM aiops.execution_start_intents WHERE run_id=%s",
                (run_id,)
            )
    with psycopg.connect(database_url) as conn:
        assert conn.execute(
            "SELECT mode,scenario_id,start_version FROM aiops.execution_start_intents "
            "WHERE run_id=%s", (run_id,)
        ).fetchone() == ("DEMO", "ci-scenario", 0)
