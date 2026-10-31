"""Revision-fenced execution admission. No real-effect executor is connected.

Atomic policy revision check + admission reservation share one SQLite transaction.
This prevents a stale revision from being newly admitted after a STOP_AUTO commit.
It does not interrupt work already executing; real effects remain disabled.
"""
import sqlite3
from datetime import datetime,timezone
try:
    from policy import autonomy_store as store
except ImportError:
    from app.policy import autonomy_store as store

def _audit(db,operation_id,revision,operation_class,reason):
    db.execute("CREATE TABLE IF NOT EXISTS admission_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL, revision INTEGER, operation_class TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL)")
    db.execute("INSERT INTO admission_decisions(operation_id,revision,operation_class,reason,recorded_at) VALUES(?,?,?,?,?)",
        (operation_id,revision,operation_class,reason,datetime.now(timezone.utc).isoformat()))

def reserve(operation_id,expected_revision,operation_class):
    if not operation_id or len(operation_id)>128:raise ValueError("invalid operation id")
    if operation_class not in ("ROUTINE_PREAPPROVED","STANDARD_CHANGE","AUTONOMOUS_REMEDIATION"):
        raise ValueError("invalid operation class")
    try:
        with store.LOCK:
            with store._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS admission_attempts (operation_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL, recorded_at TEXT NOT NULL)")
                row=db.execute("SELECT revision,mode FROM mode_history ORDER BY revision DESC LIMIT 1").fetchone()
                revision,mode=(row[0],row[1]) if row else (0,"STOP_AUTO")
                if revision!=expected_revision:
                    _audit(db,operation_id,revision,operation_class,"STALE_POLICY_REVISION")
                    return {"admitted":False,"reason":"STALE_POLICY_REVISION","revision":revision}
                if mode=="STOP_AUTO" and operation_class=="AUTONOMOUS_REMEDIATION":
                    _audit(db,operation_id,revision,operation_class,"AUTONOMY_SUSPENDED")
                    return {"admitted":False,"reason":"AUTONOMY_SUSPENDED","revision":revision}
                if mode=="FREEZE" and operation_class not in ("ROUTINE_PREAPPROVED","STANDARD_CHANGE"):
                    _audit(db,operation_id,revision,operation_class,"FREEZE_RESTRICTS_OPERATION")
                    return {"admitted":False,"reason":"FREEZE_RESTRICTS_OPERATION","revision":revision}
                if mode not in store.MODES:
                    _audit(db,operation_id,revision,operation_class,"INVALID_POLICY_MODE")
                    return {"admitted":False,"reason":"INVALID_POLICY_MODE","revision":revision}
                # Reservations are NOT permission to execute live effects.
                existing=db.execute("SELECT revision,state FROM admission_attempts WHERE operation_id=?",(operation_id,)).fetchone()
                if existing:
                    _audit(db,operation_id,revision,operation_class,"DUPLICATE_OPERATION")
                    return {"admitted":False,"reason":"DUPLICATE_OPERATION","revision":revision}
                db.execute("INSERT INTO admission_attempts VALUES (?,?,?,?)",(operation_id,revision,"RESERVED_SIMULATION_ONLY",datetime.now(timezone.utc).isoformat()))
                _audit(db,operation_id,revision,operation_class,"SIMULATION_RESERVATION_ONLY")
                return {"admitted":True,"reason":"SIMULATION_RESERVATION_ONLY","revision":revision,"execution_allowed":False}
    except (sqlite3.Error,OSError):
        return {"admitted":False,"reason":"POLICY_STORE_UNAVAILABLE","revision":None}

def summary():
    """Read-only counts; never claim LIVE execution occurred."""
    try:
        with store.LOCK:
            with store._connect() as db:
                exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admission_attempts'").fetchone()
                count=db.execute("SELECT COUNT(*) FROM admission_attempts").fetchone()[0] if exists else 0
                has_decisions=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admission_decisions'").fetchone()
                refused=db.execute("SELECT COUNT(*) FROM admission_decisions WHERE reason!=?",("SIMULATION_RESERVATION_ONLY",)).fetchone()[0] if has_decisions else 0
        return {"scope":"SIMULATION_ONLY","reservations_recorded":count,"refusals_recorded":refused,
                "live_effects_qualified":False,"healthy":True}
    except (sqlite3.Error,OSError):
        return {"scope":"SIMULATION_ONLY","reservations_recorded":None,"refusals_recorded":None,
                "live_effects_qualified":False,"healthy":False}

def decisions(limit=30):
    """Read-only bounded audit of simulation decisions."""
    if not 1<=limit<=100:raise ValueError("invalid limit")
    with store.LOCK:
        with store._connect() as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admission_decisions'").fetchone()
            if not exists:return []
            rows=db.execute("SELECT operation_id,revision,operation_class,reason,recorded_at FROM admission_decisions ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    fields=("operation_id","revision","operation_class","reason","recorded_at")
    return [dict(zip(fields,row)) for row in rows]
