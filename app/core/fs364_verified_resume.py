"""FS364 read-only composite gate. Never starts/resumes Temporal or writes GLPI.

Caller must supply fresh authoritative GLPI and backend tenant/incident records.
The SQLite check is a reference contract, not an atomic production admission.
"""
import sqlite3
from .fs364_temporal_admission import ResumeSnapshot
from .fs364_ticket_verification import Ticket147Snapshot, ticket147_matches
from .fs364_durable_admission import durable_resume_admissible


def verified_durable_resume_admissible(
    conn: sqlite3.Connection, snapshot: ResumeSnapshot,
    ticket: Ticket147Snapshot, *, expected_tenant_id: str
) -> bool:
    """Fail closed unless both independent ticket ownership and durable wait match.

    Does not replace an atomic PG16 compare-and-swap on Temporal admission.
    """
    try:
        return (
            ticket147_matches(
                snapshot.link, ticket,
                expected_tenant_id=expected_tenant_id,
                authenticated=snapshot.authenticated,
                acl_ok=snapshot.acl_ok,
            )
            and durable_resume_admissible(conn, snapshot)
        )
    except (sqlite3.Error, ValueError, TypeError, AttributeError):
        return False
