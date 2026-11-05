"""PostgreSQL 16 durable one-time ownership proof consumption (#233).

DDL is reviewed separately in sql/core_ownership_replay_ledger.sql.
Caller supplies a dedicated psycopg connection with autocommit disabled.
Do not use this adapter for human authorization until OIDC and GLPI READMY
authorities are independently integrated and the DDL is deployed.
"""
class LedgerUnavailable(RuntimeError):
    pass


def consume_once_pg16(connection, issuer, jti, expires_at):
    """Atomically consume (issuer,jti); commit before returning True.

    INSERT ON CONFLICT serializes competing consumers via the unique index.
    Failures rollback and fail closed. Do not share connection across threads.
    """
    if connection is None or getattr(connection, "autocommit", True):
        raise LedgerUnavailable("transactional PG16 connection required")
    if not isinstance(issuer, str) or not issuer or not isinstance(jti, str) or not jti:
        raise LedgerUnavailable("missing replay key")
    if type(expires_at) is not int or expires_at <= 0:
        raise LedgerUnavailable("invalid expiry")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO core_ownership_replay_ledger
                   (issuer, jti, expires_at)
                   VALUES (%s, %s, to_timestamp(%s))
                   ON CONFLICT (issuer, jti) DO NOTHING
                   RETURNING issuer""",
                (issuer, jti, expires_at),
            )
            inserted = cursor.fetchone() is not None
        connection.commit()
        return inserted
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:
            pass
        raise LedgerUnavailable("PG16 replay ledger unavailable") from exc
