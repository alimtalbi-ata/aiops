"""Final-step validation for simulation reservations; NEVER authorizes LIVE effects."""
import sqlite3
from policy import autonomy_store as store

def validate_step(operation_id,expected_revision):
    if not operation_id or len(operation_id)>128 or not isinstance(expected_revision,int) or expected_revision<0:
        raise ValueError("invalid step identity")
    try:
        with store.LOCK:
            with store._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute("SELECT revision,mode FROM mode_history ORDER BY revision DESC LIMIT 1").fetchone()
                current,mode=(row[0],row[1]) if row else (0,"STOP_AUTO")
                if current!=expected_revision:
                    return {"valid":False,"reason":"STALE_POLICY_REVISION","execution_allowed":False}
                existing=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admission_attempts'").fetchone()
                if not existing:return {"valid":False,"reason":"NO_RESERVATION","execution_allowed":False}
                found=db.execute("SELECT revision,state FROM admission_attempts WHERE operation_id=?",(operation_id,)).fetchone()
                if not found:return {"valid":False,"reason":"NO_RESERVATION","execution_allowed":False}
                if found[0]!=current:return {"valid":False,"reason":"STALE_RESERVATION","execution_allowed":False}
                if found[1]!="RESERVED_SIMULATION_ONLY":
                    return {"valid":False,"reason":"RESERVATION_INVALID","execution_allowed":False}
                if mode=="STOP_AUTO":
                    return {"valid":False,"reason":"STOP_AUTO_RECHECK","execution_allowed":False}
                if mode not in store.MODES:
                    return {"valid":False,"reason":"INVALID_MODE","execution_allowed":False}
                return {"valid":True,"reason":"SIMULATION_STEP_VALID","revision":current,"execution_allowed":False}
    except (sqlite3.Error,OSError):
        return {"valid":False,"reason":"POLICY_STORE_UNAVAILABLE","execution_allowed":False}
