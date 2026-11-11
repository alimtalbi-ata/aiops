"""Real PostgreSQL tenant isolation, revocation and bounded Runs qualification.

Only runs when AIOPS_TENANT_TEST_DSN points to an ephemeral disposable database.
Never use a production DSN: this test creates schema and synthetic fixtures.
"""
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tenant_reader", ROOT / "app/core/portal_tenant_runs.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def test_real_postgres_actor_tenant_isolation():
    dsn = os.getenv("AIOPS_TENANT_TEST_DSN")
    if not dsn:
        pytest.skip("requires dedicated ephemeral PostgreSQL")
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "db/migrations/001_schema.sql").read_text())
            cur.execute((ROOT / "db/migrations/009_portal_tenant_actor_read_groundwork.sql").read_text())
            cur.execute(
                "insert into aiops.portal_actor_tenant_grants(actor_id,tenant_id) values "
                "('alice','tenant-a'),('bob','tenant-b')"
            )
            rows = [
                (f"A-{i:03d}", "tenant-a") for i in range(101)
            ] + [("B-001", "tenant-b"), ("UNBOUND", None)]
            for run_id, tenant in rows:
                cur.execute(
                    "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                    "values (%s,'DEMO','synthetic','FAILED',%s)",
                    (run_id, "fixture-" + run_id),
                )
                if tenant:
                    cur.execute(
                        "insert into aiops.portal_run_tenant_bindings(run_id,tenant_id) values (%s,%s)",
                        (run_id, tenant),
                    )
            alice = reader.read_runs_for_verified_actor(cur, actor_id="alice")
            assert len(alice["items"]) == 100
            assert all(x["run_id"].startswith("A-") for x in alice["items"])
            assert reader.read_runs_for_verified_actor(cur, actor_id="bob")["items"][0]["run_id"] == "B-001"
            assert reader.read_runs_for_verified_actor(cur, actor_id="unknown") == {"items": []}
            assert reader.read_runs_for_verified_actor(cur, actor_id="alice", limit=17)["items"]
            assert len(reader.read_runs_for_verified_actor(cur, actor_id="alice", limit=17)["items"]) == 17
            cur.execute(
                "update aiops.portal_actor_tenant_grants set revoked_at=now() "
                "where actor_id='alice' and tenant_id='tenant-a'"
            )
            assert reader.read_runs_for_verified_actor(cur, actor_id="alice") == {"items": []}
            assert reader.read_runs_for_verified_actor(cur, actor_id="bob")["items"][0]["run_id"] == "B-001"
