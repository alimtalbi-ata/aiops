"""Fail-closed, local persisted autonomy state. Prototype: read-only integration only."""
import json,os,sqlite3,threading
from pathlib import Path
from datetime import datetime,timezone

MODES=("NORMAL","FREEZE","STOP_AUTO")
LOCK=threading.RLock()
PATH=Path(os.getenv("AIOPS_POLICY_STATE_DB","/var/lib/aiops-policy/autonomy.sqlite3"))

def _connect():
    PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(PATH),timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("CREATE TABLE IF NOT EXISTS mode_history (revision INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, changed_at TEXT NOT NULL)")
    return conn

def status():
    # Any storage error must never result in authorization.
    try:
        with LOCK:
            with _connect() as db:
                row=db.execute("SELECT revision,mode,actor,reason,changed_at FROM mode_history ORDER BY revision DESC LIMIT 1").fetchone()
        if not row:return {"mode":"STOP_AUTO","revision":0,"source":"safe_default","healthy":True}
        if row[1] not in MODES:raise ValueError("invalid persisted mode")
        return {"revision":row[0],"mode":row[1],"actor":row[2],"reason":row[3],"changed_at":row[4],"source":"sqlite","healthy":True}
    except Exception:
        return {"mode":"STOP_AUTO","revision":None,"source":"storage_unavailable","healthy":False}

def set_mode(mode,actor,reason,expected_revision):
    if mode not in MODES:raise ValueError("invalid mode")
    if not actor or len(actor)>128 or not reason or len(reason)<12 or len(reason)>1024:
        raise ValueError("actor and meaningful reason required")
    with LOCK:
        with _connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current=db.execute("SELECT revision FROM mode_history ORDER BY revision DESC LIMIT 1").fetchone()
            rev=current[0] if current else 0
            if rev!=expected_revision:raise RuntimeError("revision_conflict")
            db.execute("INSERT INTO mode_history(mode,actor,reason,changed_at) VALUES(?,?,?,?)",
                (mode,actor,reason,datetime.now(timezone.utc).isoformat()))
    return status()

def history(limit=30):
    if not 1<=limit<=100:raise ValueError("invalid limit")
    with LOCK:
        with _connect() as db:
            rows=db.execute("SELECT revision,mode,actor,reason,changed_at FROM mode_history ORDER BY revision DESC LIMIT ?",(limit,)).fetchall()
    return [dict(zip(("revision","mode","actor","reason","changed_at"),row)) for row in rows]
