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
        row = db.execute("""SELECT p.incident_id,p.run_id,p.recipe_id,p.target_id,
                   p.params_hash,p.mode,p.binding_hash,p.created_at,p.expires_at,
                   a.token_hash,a.approved_at,p.proposer_id,a.approver_id
            FROM proposals p JOIN approvals a ON a.proposal_id=p.proposal_id
            WHERE p.proposal_id=?""", (proposal_id,)).fetchone()
        # Never trust the stored binding_hash alone. A damaged SQLite record
        # could retain the old hash while changing the underlying proposal.
        expected_fields = (incident_id, run_id, recipe_id, target_id, params_hash, mode)
        if (row is None or row[:6] != expected_fields
            or not isinstance(row[6], str) or not isinstance(row[9], str)
            or not all(isinstance(row[i], (int, float)) for i in (7, 8, 10))
            or not row[7] <= row[10] <= at < row[8]
            or not 1 <= row[8] - row[7] <= 3600
            or not hmac.compare_digest(row[6], digest)
            or not hmac.compare_digest(row[9], hashlib.sha256(approval_token.encode()).hexdigest())):
            raise HITLRejected("approval missing, expired or binding mismatch")
        if db.execute("SELECT 1 FROM dry_runs WHERE proposal_id=?", (proposal_id,)).fetchone():
            raise HITLRejected("approval already consumed")
        # A valid capability token is not enough if the persisted actors or
        # append-only audit were corrupted. Validate in the same write lock
        # used to consume the token; never issue a receipt on partial evidence.
        proposer_id, approver_id = row[11:13]
        try:
            _identity(proposer_id)
            _identity(approver_id)
        except HITLRejected as exc:
            raise HITLRejected("invalid HITL actor binding") from exc
        if hmac.compare_digest(proposer_id, approver_id):
            raise HITLRejected("separation of duties required")
        audit = db.execute(
            "SELECT action,actor_id,recorded_at FROM audit WHERE proposal_id=? ORDER BY seq",
            (proposal_id,),
        ).fetchall()
        expected_audit = [
            ("PROPOSED", proposer_id, row[7]),
            ("APPROVED_SANDBOX_ONLY", approver_id, row[10]),
        ]
        if audit != expected_audit:
            raise HITLRejected("inconsistent HITL approval audit")
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


def read_status(path, *, proposal_id, now=None):
    """Read-only, redacted status for a sandbox proposal.

    This is not an authorization decision or an attested runtime proof.
    The caller must enforce authentication/tenant isolation before exposing it.
    """
    from urllib.parse import quote

    _identity(proposal_id)
    at = _now(now)
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as db:
            db.execute("PRAGMA query_only=ON")
            row = db.execute("""SELECT incident_id,run_id,recipe_id,target_id,
                params_hash,binding_hash,mode,created_at,expires_at,proposer_id
                FROM proposals WHERE proposal_id=?""", (proposal_id,)).fetchone()
            if row is None:
                raise HITLRejected("proposal not found")
            incident_id, run_id, recipe_id, target_id, params_hash, binding_hash, mode, created, expires, proposer_id = row
            if mode not in MODES or recipe_id not in RECIPES or at < created or expires <= created:
                raise HITLRejected("invalid proposal state")
            if (not isinstance(params_hash, str) or len(params_hash) != 64
                or any(c not in "0123456789abcdef" for c in params_hash)):
                raise HITLRejected("invalid stored parameter digest")
            stored_binding = {
                "incident_id": incident_id, "run_id": run_id, "recipe_id": recipe_id,
                "target_id": target_id, "params_hash": params_hash, "mode": mode,
            }
            canonical_binding = json.dumps(
                stored_binding, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
            expected_binding = hashlib.sha256(canonical_binding).hexdigest()
            if not isinstance(binding_hash, str) or not hmac.compare_digest(binding_hash, expected_binding):
                raise HITLRejected("stored proposal binding mismatch")
            approval = db.execute(
                "SELECT approver_id,approved_at FROM approvals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            receipt = db.execute(
                "SELECT receipt_id,consumed_at FROM dry_runs WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            audit = db.execute(
                "SELECT action,actor_id,recorded_at FROM audit WHERE proposal_id=? ORDER BY seq",
                (proposal_id,),
            ).fetchall()
            expected = ["PROPOSED"]
            if approval:
                expected.append("APPROVED_SANDBOX_ONLY")
            if receipt:
                expected.append("DRY_RUN_PLAN_ISSUED")
            if receipt and not approval or [a[0] for a in audit] != expected:
                raise HITLRejected("inconsistent HITL audit")
            if approval and (approval[0] == proposer_id or not created <= approval[1] < expires):
                raise HITLRejected("invalid approval timestamp")
            if receipt and not approval[1] <= receipt[1] < expires:
                raise HITLRejected("invalid receipt timestamp")
            expected_actors = [proposer_id] + ([approval[0]] if approval else []) + (
                ["sandbox-lab"] if receipt else []
            )
            if [a[1] for a in audit] != expected_actors:
                raise HITLRejected("inconsistent HITL audit actors")
            if [a[2] for a in audit] != [created] + (
                [approval[1]] if approval else []
            ) + ([receipt[1]] if receipt else []):
                raise HITLRejected("inconsistent HITL audit timestamps")
            state = ("DRY_RUN_PLANNED" if receipt else
                     "EXPIRED" if at >= expires else
                     "APPROVED_FOR_DRY_RUN_ONLY" if approval else
                     "AWAITING_HUMAN_APPROVAL")
            return {
                "schema": "aiops.hitl.sandbox-status.v1",
                "proposal_id": proposal_id, "incident_id": incident_id,
                "run_id": run_id, "recipe_id": recipe_id, "target_id": target_id,
                "params_hash": params_hash, "binding_hash": binding_hash,
                "mode": mode, "expires_at": expires, "state": state,
                "receipt_id": receipt[0] if receipt else None,
                "audit_actions": expected,
                "source": "LOCAL_SANDBOX_SQLITE_NOT_CORE",
                "synthetic": True, "runtime_authenticated": False,
                "production_qualified": False, "execution_allowed": False,
                "effect_executed": False,
                "postchecks": {name: "NOT_EXECUTED" for name in RECIPES[recipe_id]["postchecks"]},
                "rollback": {"plan": RECIPES[recipe_id]["rollback"], "status": "NOT_EXECUTED"},
            }
    except sqlite3.Error as exc:
        raise HITLRejected("HITL read store unavailable or inconsistent") from exc
