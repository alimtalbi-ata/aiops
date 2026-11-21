"""PostgreSQL-backed OIDC revocation and one-time action replay barriers.

A normal OIDC bearer token remains reusable until expiry/revocation; its JTI is
not consumed on every HTTP request. Critical approval/action IDs are separately
consumed exactly once using a unique key. All database errors fail closed.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone


def _valid_text(value: object, *, maximum: int, ascii_only: bool = False) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    return not ascii_only or value.isascii()


def _expiry(value: object):
    if type(value) is not int or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def make_oidc_jti_store(connect: Callable):
    """Build store operations using a server-owned DB-API connection factory.

    Returns (is_revoked, revoke, consume_action). The migration must be applied
    explicitly. No DDL, cleanup, or connection details are accepted per request.
    """
    if not callable(connect):
        raise ValueError("postgres_connection_factory_missing")

    def is_revoked(*, issuer: str, jti: str) -> bool:
        if not _valid_text(issuer, maximum=512) or not _valid_text(jti, maximum=512):
            return True
        try:
            connection = connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT 1 FROM aiops.oidc_jti_revocations "
                            "WHERE issuer = %s AND jti = %s AND expires_at > now()",
                            (issuer, jti),
                        )
                        return cursor.fetchone() is not None
            finally:
                connection.close()
        except Exception:
            return True

    def revoke(*, issuer: str, jti: str, expires_at: int, reason: str = "operator_revocation") -> bool:
        expiry = _expiry(expires_at)
        if (not _valid_text(issuer, maximum=512)
                or not _valid_text(jti, maximum=512)
                or expiry is None
                or not _valid_text(reason, maximum=200)):
            return False
        try:
            connection = connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO aiops.oidc_jti_revocations "
                            "(issuer, jti, expires_at, reason) VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (issuer, jti) DO UPDATE SET "
                            "expires_at = GREATEST(aiops.oidc_jti_revocations.expires_at, EXCLUDED.expires_at), "
                            "reason = EXCLUDED.reason",
                            (issuer, jti, expiry, reason),
                        )
                return True
            finally:
                connection.close()
        except Exception:
            return False

    def consume_action(*, issuer: str, jti: str, action_id: str, expires_at: int) -> bool:
        """Atomically consume a token/action pair once; concurrent duplicates deny."""
        expiry = _expiry(expires_at)
        if (not _valid_text(issuer, maximum=512)
                or not _valid_text(jti, maximum=512)
                or not _valid_text(action_id, maximum=200, ascii_only=True)
                or expiry is None):
            return False
        try:
            connection = connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO aiops.oidc_sensitive_action_consumptions "
                            "(issuer, jti, action_id, expires_at) "
                            "VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (issuer, jti, action_id) DO NOTHING "
                            "RETURNING action_id",
                            (issuer, jti, action_id, expiry),
                        )
                        row = cursor.fetchone()
                        return (isinstance(row, (tuple, list))
                                and len(row) == 1 and row[0] == action_id)
            finally:
                connection.close()
        except Exception:
            return False

    return is_revoked, revoke, consume_action
