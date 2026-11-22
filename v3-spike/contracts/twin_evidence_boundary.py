"""Synthetic Twin/Evidence correlation boundary. No production authorization."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import sqlite3

@dataclass(frozen=True)
class TwinEvidenceView:
    tenant: str
    instance: str
    event: str
    revision: str
    twin_payload: str
    evidence_payload: str
    evidence_sha256: str

def correlate(conn, *, tenant, instance, principal, event, revision, evidence_sha256, inspect=None):
    """Return only SIMULATE_ONLY or DENY. Inspector receives immutable data, never conn.

    Python closures are not a sandbox: truly hostile callbacks need process isolation.
    Caller must own the SQLite connection; external side effects are out of scope.
    """
    started = False
    try:
        if not all(isinstance(v, str) and v for v in
                   (tenant, instance, principal, event, revision, evidence_sha256)):
            return {"decision": "DENY", "reason": "invalid_input"}
        if len(evidence_sha256) != 64 or conn.in_transaction:
            return {"decision": "DENY", "reason": "invalid_state"}
        conn.execute("BEGIN IMMEDIATE")
        started = True
        acl = conn.execute("SELECT allowed FROM acl WHERE tenant=? AND principal=?",
                           (tenant, principal)).fetchone()
        twin = conn.execute("SELECT revision,payload FROM twin WHERE tenant=? AND instance=?",
                            (tenant, instance)).fetchone()
        ev = conn.execute("SELECT revision,digest,payload FROM evidence "
                          "WHERE tenant=? AND instance=? AND event=?",
                          (tenant, instance, event)).fetchone()
        if acl != (1,) or twin is None or ev is None or twin[0] != revision or ev[0] != revision:
            return {"decision": "DENY", "reason": "acl_or_revision"}
        computed = hashlib.sha256(ev[2].encode("utf-8")).hexdigest()
        if not hmac.compare_digest(computed, ev[1]) or not hmac.compare_digest(computed, evidence_sha256):
            return {"decision": "DENY", "reason": "digest"}
        view = TwinEvidenceView(tenant, instance, event, revision, twin[1], ev[2], computed)
        if inspect is not None and inspect(view) is not True:
            return {"decision": "DENY", "reason": "inspection"}
        if conn.execute("SELECT allowed FROM acl WHERE tenant=? AND principal=?",
                        (tenant, principal)).fetchone() != (1,):
            return {"decision": "DENY", "reason": "revoked"}
        identity = json.dumps([tenant, instance, event, revision], separators=(",", ":"))
        return {"decision": "SIMULATE_ONLY", "contract_version": "v3-twin-evidence-synthetic-1",
                "tenant": tenant, "instance": instance, "event": event, "revision": revision,
                "evidence_sha256": computed,
                "correlation": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "production_authorized": False}
    except Exception:
        return {"decision": "DENY", "reason": "exception"}
    finally:
        if started:
            try:
                if conn.in_transaction:
                    conn.rollback()
            except sqlite3.Error:
                pass
