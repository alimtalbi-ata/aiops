"""Reference single-use admission claim, NOT a Temporal resume or PG16 implementation.

All checks and the claim occur under one SQLite write transaction. This only
serializes participants using this same database; Temporal state and GLPI are
external and MUST be rechecked atomically by the production coordinator.
"""
import sqlite3
from .fs364_verified_resume import verified_durable_resume_admissible

CLAIM_SCHEMA = """
CREATE TABLE IF NOT EXISTS fs364_resume_claims (
 run_id TEXT PRIMARY KEY,
 state_version TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE,
 claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def claim_resume(conn, snapshot, ticket, *, expected_tenant_id, state_version, request_id):
    """Return True only for a newly inserted claim; all replays return False.

    Never calls Temporal, GLPI, Worker or a filesystem mutator.
    The caller must verify that the supplied state_version is authoritative.
    """
    if (not isinstance(state_version, str) or not state_version.strip()
            or state_version != state_version.strip()
            or not isinstance(request_id, str) or not request_id.strip()
            or request_id != request_id.strip()):
        return False
    # Never roll back a transaction owned by the caller. A nested BEGIN would
    # fail, and the generic exception handler must not destroy caller writes.
    if conn.in_transaction:
        return False
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(CLAIM_SCHEMA)
        if not verified_durable_resume_admissible(
            conn, snapshot, ticket, expected_tenant_id=expected_tenant_id
        ):
            conn.rollback()
            return False
        row = conn.execute(
            "SELECT state_version, request_id FROM fs364_resume_claims WHERE run_id=?",
            (snapshot.link.run_id,),
        ).fetchone()
        if row:
            conn.rollback()
            # An identical replay is not a new dispatch permit.
            # Returning True here could cause a second Temporal signal.
            return False
        conn.execute(
            "INSERT INTO fs364_resume_claims(run_id,state_version,request_id) VALUES (?,?,?)",
            (snapshot.link.run_id, state_version, request_id),
        )
        conn.commit()
        return True
    except (sqlite3.Error, ValueError, TypeError, AttributeError):
        if conn.in_transaction:
            conn.rollback()
        return False
