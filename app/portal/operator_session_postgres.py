"""Shared session adapter, not wired to HTTP. connect must return a fresh
psycopg-compatible connection using a dedicated restricted runtime role.
Schema migration and integration qualification are external prerequisites.
"""
import secrets
from contextlib import closing

from portal.operator_session import OperatorSessions
from portal.incident_read_policy import IncidentReadPrincipal, may_read_incident


class PostgresOperatorSessions:
    def __init__(self, connect):
        self._connect = connect

    def issue(self, principal):
        if type(principal) is not IncidentReadPrincipal or not may_read_incident(principal, principal.tenant):
            raise ValueError("unqualified principal")
        token = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn, conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO portal_operator_sessions
                (token_digest, subject, tenant, role, issued_at, touched_at, absolute_expires_at)
                SELECT %s, %s, %s, %s, t, t, t + interval '8 hours'
                FROM (SELECT clock_timestamp() AS t) AS stamp""",
                (OperatorSessions._key(token), principal.subject, principal.tenant, principal.role),
            )
        return token

    def resolve(self, token):
        key = OperatorSessions._key(token)
        if key is None:
            return None
        with closing(self._connect()) as conn, conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE portal_operator_sessions
                SET touched_at = clock_timestamp()
                WHERE token_digest = %s
                  AND touched_at <= clock_timestamp()
                  AND touched_at > clock_timestamp() - interval '15 minutes'
                  AND absolute_expires_at > clock_timestamp()
                RETURNING subject, tenant, role""",
                (key,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        principal = IncidentReadPrincipal(*row)
        return principal if may_read_incident(principal, principal.tenant) else None

    def revoke(self, token):
        key = OperatorSessions._key(token)
        if key is not None:
            with closing(self._connect()) as conn, conn, conn.cursor() as cur:
                cur.execute("DELETE FROM portal_operator_sessions WHERE token_digest = %s", (key,))
