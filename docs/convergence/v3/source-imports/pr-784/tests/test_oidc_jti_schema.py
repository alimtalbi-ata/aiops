from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "db/migrations/010_oidc_jti_revocation_and_action_replay.sql").read_text().lower()


def test_oidc_jti_revocation_is_scoped_by_issuer_and_jti():
    assert "create table if not exists aiops.oidc_jti_revocations" in SQL
    assert "primary key (issuer, jti)" in SQL
    assert "expires_at timestamptz not null" in SQL
    assert "revoked_at timestamptz not null" in SQL


def test_sensitive_actions_have_a_separate_atomic_replay_key():
    assert "create table if not exists aiops.oidc_sensitive_action_consumptions" in SQL
    assert "primary key (issuer, jti, action_id)" in SQL
    assert "consumed_at timestamptz not null" in SQL


def test_migration_contains_no_tokens_secrets_or_automatic_cleanup():
    executable = "\n".join(line for line in SQL.splitlines() if not line.lstrip().startswith("--"))
    assert "access_token" not in executable
    assert "signing_key" not in executable
    assert "delete from" not in executable
    assert "truncate " not in executable
