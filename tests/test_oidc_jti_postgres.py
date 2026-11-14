"""PostgreSQL-backed OIDC revocation and one-time action race qualification.

Runs only against the dedicated loopback tenant_isolation CI database.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from shared.oidc_jti_store import make_oidc_jti_store


def test_postgres_oidc_revocation_and_action_replay_are_durable_and_atomic():
    dsn = os.getenv("AIOPS_TENANT_TEST_DSN")
    if not dsn:
        pytest.skip("requires dedicated ephemeral PostgreSQL")
    parsed = urlsplit(dsn)
    assert parsed.scheme in {"postgresql", "postgres"}
    assert parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    assert parsed.path == "/tenant_isolation"
    assert parsed.username == "tenant_ci"
    assert parsed.port == 5432

    import psycopg

    def connect():
        return psycopg.connect(dsn)

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute((ROOT / "db/migrations/010_oidc_jti_revocation_and_action_replay.sql").read_text())

    is_revoked, revoke, consume = make_oidc_jti_store(connect)
    issuer = "https://ci.invalid/issuer"
    jti = "ci-jti-" + os.urandom(12).hex()
    action = "approve:INC-" + os.urandom(8).hex()
    expiry = 2_100_000_000

    assert is_revoked(issuer=issuer, jti=jti) is False
    assert revoke(issuer=issuer, jti=jti, expires_at=expiry, reason="ci_test_revocation")
    assert is_revoked(issuer=issuer, jti=jti) is True

    # A valid JWT remains reusable for ordinary reads; a specific sensitive
    # action is consumed once and concurrent attempts have exactly one winner.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda _: consume(issuer=issuer, jti=jti, action_id=action, expires_at=expiry),
            range(8),
        ))
    assert sum(results) == 1
