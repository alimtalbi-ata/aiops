"""Read-only FS364 durable correlation check before any Temporal admission.

This is a reference SQLite gate, not a production PG16 adapter. No side effects.
The caller must supply independently verified current GLPI/Policy/ACL facts.
"""
import sqlite3
from .fs364_correlation import Link, validate
from .fs364_temporal_admission import ResumeSnapshot, resume_admissible


def durable_resume_admissible(conn: sqlite3.Connection, snapshot: ResumeSnapshot) -> bool:
    """Require an exact committed correlation row as well as the wait-state gate."""
    if not resume_admissible(snapshot):
        return False
    try:
        validate(snapshot.link)
        row = conn.execute(
            "SELECT fingerprint, incident_id, run_id, evidence_id, ticket_id, mode "
            "FROM fs364_links WHERE fingerprint=?",
            (snapshot.link.fingerprint,),
        ).fetchone()
        expected = snapshot.link
        return row is not None and tuple(row) == (
            expected.fingerprint, expected.incident_id, expected.run_id,
            expected.evidence_id, expected.ticket_id, expected.mode,
        )
    except (sqlite3.Error, ValueError, TypeError, AttributeError):
        return False
