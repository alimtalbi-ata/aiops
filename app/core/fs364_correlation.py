"""FS.364 correlation ledger: pure, fail-closed, no GLPI/Temporal side effects.

An integration adapter must authenticate the caller, verify the existing GLPI ticket
independently and persist the resulting evidence before invoking bind().
"""
import sqlite3
from dataclasses import dataclass

TICKET_ID = 147
SCHEMA = """
CREATE TABLE IF NOT EXISTS fs364_links (
 fingerprint TEXT PRIMARY KEY,
 incident_id TEXT NOT NULL UNIQUE,
 run_id TEXT NOT NULL UNIQUE,
 evidence_id TEXT NOT NULL UNIQUE,
 ticket_id INTEGER NOT NULL CHECK(ticket_id = 147),
 mode TEXT NOT NULL CHECK(mode IN ('DEMO','LIVE')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class ContractRefused(ValueError):
    pass

@dataclass(frozen=True)
class Link:
    fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    ticket_id: int
    mode: str

def validate(link: Link) -> None:
    if link.ticket_id != TICKET_ID or link.mode not in ("DEMO", "LIVE"):
        raise ContractRefused("ticket or mode mismatch")
    if any(not isinstance(v, str) or not v.strip() or v != v.strip()
           for v in (link.fingerprint, link.incident_id, link.run_id, link.evidence_id)):
        raise ContractRefused("missing or malformed correlation identifier")

def bind(conn: sqlite3.Connection, link: Link, *, verified_ticket: bool,
         authenticated: bool, stop_auto: bool = True) -> Link:
    """Atomic insert/replay. No ticket creation, workflow launch or LIVE effect.

    verified_ticket must come from an authenticated read of GLPI ticket 147,
    not from caller-provided ticket_id alone. Fail closed on any ambiguity.
    """
    validate(link)
    if authenticated is not True or verified_ticket is not True or stop_auto is not True:
        raise ContractRefused("authentication, ticket verification or STOP_AUTO missing")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(SCHEMA)
        existing = conn.execute(
            "SELECT fingerprint, incident_id, run_id, evidence_id, ticket_id, mode "
            "FROM fs364_links WHERE fingerprint=? OR incident_id=? OR run_id=? OR evidence_id=?",
            (link.fingerprint, link.incident_id, link.run_id, link.evidence_id),
        ).fetchall()
        if existing:
            if len(existing) != 1 or tuple(existing[0]) != (
                link.fingerprint, link.incident_id, link.run_id,
                link.evidence_id, link.ticket_id, link.mode
            ):
                raise ContractRefused("conflicting correlation replay")
        else:
            conn.execute(
                "INSERT INTO fs364_links "
                "(fingerprint,incident_id,run_id,evidence_id,ticket_id,mode) "
                "VALUES (?,?,?,?,?,?)",
                (link.fingerprint, link.incident_id, link.run_id,
                 link.evidence_id, link.ticket_id, link.mode),
            )
        conn.commit()
        return link
    except Exception:
        conn.rollback()
        raise

def launch_allowed(*, mode: str, authenticated: bool, acl_ok: bool,
                   stop_auto: bool, policy_decision: str, human_approval: bool) -> bool:
    """Conservative gate; no launch implementation and no synthetic approval."""
    return (mode == "DEMO" and authenticated is True and acl_ok is True
            and stop_auto is False and policy_decision == "ALLOW"
            and human_approval is True)

def temporal_resume_allowed(*, mode: str, same_run: bool, mode_match: bool,
                            authenticated: bool, acl_ok: bool, stop_auto: bool,
                            policy_decision: str, human_answer_verified: bool,
                            approval_specific: bool) -> bool:
    """A Policy refusal is terminal; a real human response alone is insufficient."""
    return (mode == "DEMO" and same_run is True and mode_match is True
            and authenticated is True and acl_ok is True and stop_auto is False
            and policy_decision == "ALLOW" and human_answer_verified is True
            and approval_specific is True)
