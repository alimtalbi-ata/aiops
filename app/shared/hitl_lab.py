"""Durable, sandbox-only HITL approval and dry-run receipts.

This library is not an HTTP auth boundary or a LIVE remediation executor.
Callers MUST authenticate the actor/role before passing them to this module.
"""
import hashlib
from contextlib import contextmanager
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timezone

MODES = frozenset({"DEMO", "REPLAY", "STORY"})
RECIPES = {
    "acme.demo.restart-service.v1": {"param": "service", "postchecks": ["service_health", "business_slo"], "rollback": "restore prior synthetic service state"},
    "acme.demo.failover-link.v1": {"param": "link", "postchecks": ["link_health", "path_redundancy"], "rollback": "restore prior synthetic path selection"},
}


class HITLRejected(ValueError):
    """A failed safety check; no effect has been performed."""


def _now(value):
    dt = datetime.now(timezone.utc) if value is None else value
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise HITLRejected("timezone-aware clock required")
    return dt.astimezone(timezone.utc).timestamp()


def _identity(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or value.strip() != value or any(c.isspace() for c in value):
        raise HITLRejected("invalid identifier")
    return value


def _canonical(params, recipe_id):
    if not isinstance(params, dict) or not params:
        raise HITLRejected("nonempty object parameters required")
    required = RECIPES[recipe_id]["param"]
    if set(params) != {required} or not isinstance(params[required], str):
        raise HITLRejected("recipe parameter schema mismatch")
    _identity(params[required])
    try:
        data = json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise HITLRejected("invalid parameters") from exc
    if len(data.encode()) > 4096:
        raise HITLRejected("parameters too large")
    if any(k.lower() in ("command", "shell", "script", "exec", "sudo") for k in params if isinstance(k, str)):
        raise HITLRejected("free-form commands prohibited")
    return data


@contextmanager
def _connect(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        yield db
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    with _connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS proposals (
                proposal_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL,
                run_id TEXT NOT NULL, recipe_id TEXT NOT NULL, target_id TEXT NOT NULL,
                params_hash TEXT NOT NULL, binding_hash TEXT NOT NULL,
                proposer_id TEXT NOT NULL, mode TEXT NOT NULL, created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                proposal_id TEXT PRIMARY KEY REFERENCES proposals(proposal_id),
                approver_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
                approved_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dry_runs (
                proposal_id TEXT PRIMARY KEY REFERENCES approvals(proposal_id),
                receipt_id TEXT NOT NULL UNIQUE, consumed_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL,
                action TEXT NOT NULL, actor_id TEXT NOT NULL, recorded_at REAL NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS proposals_immutable_update BEFORE UPDATE ON proposals BEGIN SELECT RAISE(ABORT, 'immutable proposal'); END;
            CREATE TRIGGER IF NOT EXISTS proposals_immutable_delete BEFORE DELETE ON proposals BEGIN SELECT RAISE(ABORT, 'immutable proposal'); END;
            CREATE TRIGGER IF NOT EXISTS approvals_immutable_update BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT, 'immutable approval'); END;
            CREATE TRIGGER IF NOT EXISTS approvals_immutable_delete BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT, 'immutable approval'); END;
            CREATE TRIGGER IF NOT EXISTS dry_runs_immutable_update BEFORE UPDATE ON dry_runs BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
            CREATE TRIGGER IF NOT EXISTS dry_runs_immutable_delete BEFORE DELETE ON dry_runs BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
            CREATE TRIGGER IF NOT EXISTS audit_immutable_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'immutable audit'); END;
            CREATE TRIGGER IF NOT EXISTS audit_immutable_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'immutable audit'); END;
        """)


def propose(path, *, incident_id, run_id, recipe_id, target_id, params, proposer_id,
            mode="DEMO", ttl_seconds=300, now=None):
    """Store an immutable proposed action. Only an allowlisted sandbox recipe is accepted."""
    for v in (incident_id, run_id, recipe_id, target_id, proposer_id):
        _identity(v)
    if mode not in MODES or recipe_id not in RECIPES:
        raise HITLRejected("sandbox mode and allowlisted recipe required")
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 3600:
        raise HITLRejected("invalid approval TTL")
    canonical = _canonical(params, recipe_id)
    params_hash = hashlib.sha256(canonical.encode()).hexdigest()
    binding = {"incident_id": incident_id, "run_id": run_id, "recipe_id": recipe_id,
               "target_id": target_id, "params_hash": params_hash, "mode": mode}
    binding_hash = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    created = _now(now)
    proposal_id = secrets.token_hex(16)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (proposal_id, incident_id, run_id, recipe_id, target_id, params_hash,
                    binding_hash, proposer_id, mode, created, created + ttl_seconds))
        db.execute("INSERT INTO audit(proposal_id,action,actor_id,recorded_at) VALUES (?,?,?,?)",
                   (proposal_id, "PROPOSED", proposer_id, created))
        db.commit()
    return {"proposal_id": proposal_id, "binding_hash": binding_hash, "params_hash": params_hash,
            "expires_at": created + ttl_seconds, "mode": mode, "state": "AWAITING_HUMAN_APPROVAL",
            "execution_allowed": False}


def approve(path, *, proposal_id, approver_id, approver_role, now=None):
    """Issue a one-use capability to an authenticated, distinct human approver."""
    _identity(proposal_id)
    _identity(approver_id)
    if approver_role != "approver":
        raise HITLRejected("verified approver role required")
    at = _now(now)
    token = secrets.token_urlsafe(32)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT proposer_id,created_at,expires_at FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None or at >= row[2] or at < row[1]:
            raise HITLRejected("proposal missing or expired")
        if hmac.compare_digest(row[0], approver_id):
            raise HITLRejected("separation of duties required")
        if db.execute("SELECT 1 FROM approvals WHERE proposal_id=?", (proposal_id,)).fetchone():
            raise HITLRejected("already approved")
        db.execute("INSERT INTO approvals VALUES (?,?,?,?)",
                   (proposal_id, approver_id, hashlib.sha256(token.encode()).hexdigest(), at))
        db.execute("INSERT INTO audit(proposal_id,action,actor_id,recorded_at) VALUES (?,?,?,?)",
                   (proposal_id, "APPROVED_SANDBOX_ONLY", approver_id, at))
        db.commit()
    return {"approval_token": token, "proposal_id": proposal_id, "execution_allowed": False,
            "state": "APPROVED_FOR_DRY_RUN_ONLY"}


def dry_run(path, *, proposal_id, approval_token, incident_id, run_id, recipe_id,
            target_id, params, mode="DEMO", now=None):
    """Consume approval atomically and emit a *plan*, never run commands or postchecks."""
    for v in (proposal_id, incident_id, run_id, recipe_id, target_id):
        _identity(v)
    if not isinstance(approval_token, str) or not approval_token:
        raise HITLRejected("approval token required")
    if mode not in MODES or recipe_id not in RECIPES:
        raise HITLRejected("sandbox recipe required")
    params_hash = hashlib.sha256(_canonical(params, recipe_id).encode()).hexdigest()
    binding = {"incident_id": incident_id, "run_id": run_id, "recipe_id": recipe_id,
               "target_id": target_id, "params_hash": params_hash, "mode": mode}
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    at = _now(now)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT p.binding_hash,p.expires_at,a.token_hash,a.approved_at
            FROM proposals p JOIN approvals a ON a.proposal_id=p.proposal_id
            WHERE p.proposal_id=?""", (proposal_id,)).fetchone()
        if row is None or at >= row[1] or at < row[3] or not hmac.compare_digest(row[0], digest) or not hmac.compare_digest(row[2], hashlib.sha256(approval_token.encode()).hexdigest()):
            raise HITLRejected("approval missing, expired or binding mismatch")
        if db.execute("SELECT 1 FROM dry_runs WHERE proposal_id=?", (proposal_id,)).fetchone():
            raise HITLRejected("approval already consumed")
        receipt_id = secrets.token_hex(16)
        db.execute("INSERT INTO dry_runs VALUES (?,?,?)", (proposal_id, receipt_id, at))
        db.execute("INSERT INTO audit(proposal_id,action,actor_id,recorded_at) VALUES (?,?,?,?)",
                   (proposal_id, "DRY_RUN_PLAN_ISSUED", "sandbox-lab", at))
        db.commit()
    recipe = RECIPES[recipe_id]
    return {"receipt_id": receipt_id, "proposal_id": proposal_id, "binding_hash": digest,
            "mode": mode, "state": "DRY_RUN_PLANNED", "synthetic": True,
            "effect_executed": False, "execution_allowed": False,
            "postchecks": {name: "NOT_EXECUTED" for name in recipe["postchecks"]},
            "rollback": {"plan": recipe["rollback"], "status": "NOT_EXECUTED"}}
