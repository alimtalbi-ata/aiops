"""Guard the additive schema: no implicit tenant grants or historical backfill."""
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "db/migrations/009_portal_tenant_actor_read_groundwork.sql").read_text().lower()


def test_explicit_actor_grants_and_revocation_are_modeled():
    assert "create table if not exists aiops.portal_actor_tenant_grants" in SQL
    assert "primary key (actor_id, tenant_id)" in SQL
    assert "revoked_at timestamptz" in SQL
    assert "g.revoked_at is null" in SQL


def test_runs_require_explicit_tenant_binding():
    assert "create table if not exists aiops.portal_run_tenant_bindings" in SQL
    assert "run_id text primary key references aiops.runs(run_id)" in SQL
    assert "join aiops.portal_run_tenant_bindings" in SQL
    assert "join aiops.portal_actor_tenant_grants" in SQL


def test_migration_does_not_grant_or_backfill():
    executable = "\n".join(
        line for line in SQL.splitlines() if not line.lstrip().startswith("--")
    )
    assert "insert into" not in executable
    assert "update aiops.runs" not in executable
    assert "alter table aiops.runs" not in executable
    assert "create policy" not in executable
