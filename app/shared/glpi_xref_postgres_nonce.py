"""Durable PostgreSQL replay barrier for signed GLPI cross-reference events.

Install the SQL migration explicitly before wiring this adapter. The callback
requires a server-owned transaction-capable connection factory, not a request
parameter. It commits an atomic unique-key insert before returning success.
Never store the signing secret or untrusted event body in this table.
"""
from collections.abc import Callable
from datetime import datetime, timezone

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS aiops.glpi_xref_consumed_nonces (
    tenant_id text NOT NULL,
    nonce text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, nonce)
);
"""


def make_postgres_nonce_consumer(connect: Callable):
    """Create an atomic insert-if-absent replay barrier.

    connect() returns a DB-API connection supporting context-manager
    transactions and cursor(). The unique constraint is mandatory.
    This adapter never auto-creates the schema or prunes old nonces:
    deleting expired rows can allow replay if a still-valid signed event
    is presented; retention must exceed maximum signed lifetime and skew.
    """
    if not callable(connect):
        raise ValueError("postgres_connection_factory_missing")

    def consume_nonce(*, tenant_id, nonce, expires_at):
        if (not isinstance(tenant_id, str) or not tenant_id.strip()
                or len(tenant_id) > 128
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in tenant_id)
                or not isinstance(nonce, str)
                or not 16 <= len(nonce) <= 128
                or not nonce.isascii() or not nonce.isalnum()
                or type(expires_at) is not int or expires_at <= 0):
            return False
        try:
            # Reject timestamps PostgreSQL cannot represent before opening a DB connection.
            expiry = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return False
        try:
            connection = connect()
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO aiops.glpi_xref_consumed_nonces "
                            "(tenant_id, nonce, expires_at) "
                            "VALUES (%s, %s, %s) "
                            "ON CONFLICT (tenant_id, nonce) DO NOTHING "
                            "RETURNING nonce",
                            (tenant_id, nonce,
                             expiry),
                        )
                        row = cursor.fetchone()
                        # Only the exact inserted nonce proves successful
                        # insert; a malformed DB result must fail closed.
                        inserted = (isinstance(row, (tuple, list))
                                    and len(row) == 1 and row[0] == nonce)
                # Transaction context exited: commit must have succeeded.
                return inserted
            finally:
                # psycopg2 connection contexts commit/rollback but do not close.
                connection.close()
        except Exception:
            # Never permit a replay on database outage or uncertain commit.
            return False

    return consume_nonce
