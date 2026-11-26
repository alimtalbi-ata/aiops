"""Persistent, manually advanced synthetic enterprise clock; no operational action."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from enterprise_context import P, ROOT, digest

WORLD = "ACME-E2-V1"
EPOCH = datetime(2026,1,1,9,tzinfo=timezone.utc)
PHASES = ("NOMINAL","CHANGE","DEGRADED","MODEL_RECOVERY")
MAX_TICK = 10000

def timestamp(tick, seconds=0):
    return (EPOCH+timedelta(minutes=tick,seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

def model(tick):
    if type(tick) is not int or not 1<=tick<=MAX_TICK:
        raise ValueError("invalid tick")
    cycle=(tick-1)//4+1
    phase=PHASES[(tick-1)%4]
    baseline=35+int(hashlib.sha256(f"{WORLD}:{cycle}".encode()).hexdigest()[:8],16)%11
    value=baseline*4 if phase=="DEGRADED" else baseline
    return {"world_id":WORLD,"tick":tick,"cycle":cycle,"phase":phase,"simulated_at":timestamp(tick),
            "asset_id":P+"ASSET-PAR","application_id":P+"APP-PAY",
            "modeled_latency_ms":value,"baseline_ms":baseline,"measurement_kind":"MODEL_GENERATED",
            "operational_decision":"DENY","production_authorized":False}

def batch(step):
    tick=step["tick"]
    if step!=model(tick) or step["phase"]!="DEGRADED":
        raise ValueError("degraded model required")
    scope={"asset_id":step["asset_id"],"application_id":step["application_id"]}
    base={"kind":"metric","source":"enterprise-clock-e2","resource":ROOT,"severity":"critical","tenant":"synthetic-demo","synthetic":True}
    prefix=f"e2-{tick}-"
    return [
        dict(base,id=prefix+"baseline",enterprise=dict(scope,occurred_at=timestamp(tick-2)),observation={"metric":"latency_ms","phase":"baseline","value":step["baseline_ms"]}),
        dict(base,id=prefix+"metric",enterprise=dict(scope,occurred_at=timestamp(tick)),observation={"metric":"latency_ms","phase":"incident","value":step["modeled_latency_ms"]}),
        dict(base,id=prefix+"log",kind="log",enterprise=dict(scope,occurred_at=timestamp(tick,1),group_id=P+"GROUP-FIN",user_id=P+"USER-FIN-01",message="Model-generated user report: slow payments")),
        dict(base,id=prefix+"event",kind="event",enterprise=dict(scope,occurred_at=timestamp(tick,2),message="Model-generated latency alarm after scheduled synthetic change")),
    ]

class EnterpriseClock:
    def __init__(self, root):
        root=Path(root)
        if not root.is_absolute() or root==Path("/") or root.resolve()!=root or not root.is_dir() or root.stat().st_uid!=os.getuid():
            raise ValueError("private dedicated root required")
        folder=root/"enterprise-e2"
        folder.mkdir(mode=0o700,exist_ok=True)
        info=folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ValueError("unsafe clock directory")
        self.path=folder/"world.sqlite3"
        if not self.path.exists():
            try:
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
                os.close(fd)
            except FileExistsError:
                pass
        info=self.path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077 or info.st_nlink!=1:
            raise ValueError("unsafe clock database")
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS journal(tick INTEGER PRIMARY KEY, step TEXT NOT NULL, step_hash TEXT NOT NULL, receipt TEXT, UNIQUE(step_hash))")
            db.execute("CREATE TABLE IF NOT EXISTS measured(tick INTEGER PRIMARY KEY REFERENCES journal(tick), batches TEXT NOT NULL, batch_hash TEXT NOT NULL, receipt TEXT)")
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db
    @staticmethod
    def decode(row):
        tick,raw,h,receipt=row
        step=json.loads(raw)
        if step!=model(tick) or digest(step)!=h:
            raise ValueError("corrupt model journal")
        return {**step,"step_sha256":h,"publication":json.loads(receipt) if receipt is not None else None}
    def status(self):
        with closing(self.connect()) as db:
            rows=db.execute("SELECT tick,step,step_hash,receipt FROM journal ORDER BY tick DESC LIMIT 20").fetchall()
            recent=[self.decode(r) for r in reversed(rows)]
            for item in recent:
                capture=db.execute("SELECT batches,batch_hash,receipt FROM measured WHERE tick=?",(item["tick"],)).fetchone()
                if capture is not None:
                    item["measured_capture"]=self.decode_capture(capture)
        latest=recent[-1] if recent else None
        return {"classification":"SYNTHETIC_ENTERPRISE_CLOCK_E2","world_id":WORLD,
                "current_tick":latest["tick"] if latest else 0,"pending":bool(latest and latest["publication"] is None),
                "latest":latest,"recent":recent,"clock_mode":"MANUAL_LOGICAL_TIME","production_authorized":False,"operational_decision":"DENY"}
    def advance(self, expected_tick, publish):
        if type(expected_tick) is not int or not 1<=expected_tick<=MAX_TICK:
            raise ValueError("invalid expected tick")
        # Durable outbox: record the deterministic step before remote writes.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT tick,receipt FROM journal ORDER BY tick DESC LIMIT 1").fetchone()
            last=latest[0] if latest else 0
            if expected_tick==last+1 and db.execute("SELECT 1 FROM measured WHERE receipt IS NULL LIMIT 1").fetchone():
                raise ValueError("pending measurement publication must be retried")
            if expected_tick==last+1 and (latest is None or latest[1] is not None):
                step=model(expected_tick)
                db.execute("INSERT INTO journal(tick,step,step_hash) VALUES(?,?,?)",(expected_tick,json.dumps(step,sort_keys=True),digest(step)))
            elif expected_tick!=last:
                raise ValueError("stale or skipped tick")
        # Serialize publication; on failure the pending row is left for retry.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(expected_tick,)).fetchone()
            result=self.decode(row)
            if result["publication"] is not None:
                return result
            step=model(expected_tick)
            if step["phase"]=="DEGRADED":
                response=publish(batch(step))
                run=response["core"]["run"]
                refs=response["stored_evidence"]
                if (response.get("production_authorized") is not False or run["mode"]!="DEMO"
                    or not re.fullmatch(r"RUN-[A-F0-9]{16}",run["run_id"])
                    or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",run["incident_id"])
                    or len(refs)!=4 or len({r["evidence_id"] for r in refs})!=4
                    or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs)):
                    raise ValueError("unverified publication")
                receipt={"state":"PUBLISHED","run_id":run["run_id"],"incident_id":run["incident_id"],"evidence":refs}
            else:
                receipt={"state":"MODEL_ONLY","run_id":None,"incident_id":None,"evidence":[]}
            db.execute("UPDATE journal SET receipt=? WHERE tick=?",(json.dumps(receipt,sort_keys=True),expected_tick))
            result["publication"]=receipt
            return result

    @staticmethod
    def decode_capture(row):
        raw,h,receipt=row
        batches=json.loads(raw)
        if digest(batches)!=h:
            raise ValueError("corrupt measurement snapshot")
        return {"batch_sha256":h,"state":"PENDING" if receipt is None else "PUBLISHED",
                "incidents":[] if receipt is None else json.loads(receipt)}

    def capture(self, expected_tick, collect, publish):
        """Attach actual loopback samples to a committed model degradation, not a new clock."""
        if type(expected_tick) is not int or not 1<=expected_tick<=MAX_TICK:
            raise ValueError("invalid capture tick")
        from enterprise_context import CAPTURE_ROOTS
        from ingestion_demo import ingest
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT tick,step,step_hash,receipt FROM journal ORDER BY tick DESC LIMIT 1").fetchone()
            if latest is None or latest[0]!=expected_tick:
                raise ValueError("capture requires current tick")
            step=self.decode(latest)
            if step["phase"]!="DEGRADED" or step["publication"] is None:
                raise ValueError("committed degraded model required")
            saved=db.execute("SELECT batches,batch_hash,receipt FROM measured WHERE tick=?",(expected_tick,)).fetchone()
            if saved is None:
                batches=collect()
                if not isinstance(batches,list) or len(batches)!=2:
                    raise ValueError("two measurement batches required")
                roots=set()
                for rows in batches:
                    normalized=ingest(rows)["incidents"]
                    if len(normalized)!=1 or len(rows)!=4 or len(normalized[0]["evidence"])!=4:
                        raise ValueError("invalid measured incident")
                    roots.add(normalized[0]["resource"])
                    if any("measurement" not in r["enterprise"] for r in rows if r["kind"]=="metric") or sum(r["kind"]=="metric" for r in rows)!=2:
                        raise ValueError("measured samples required")
                if roots!=CAPTURE_ROOTS:
                    raise ValueError("distinct asset roots required")
                db.execute("INSERT INTO measured(tick,batches,batch_hash) VALUES(?,?,?)",
                           (expected_tick,json.dumps(batches,sort_keys=True),digest(batches)))
        # Durable raw batches survive a failed remote publication. Both writes are idempotent.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT batches,batch_hash,receipt FROM measured WHERE tick=?",(expected_tick,)).fetchone()
            result=self.decode_capture(row)
            if result["state"]=="PUBLISHED":
                return result
            receipts=[]
            for rows in json.loads(row[0]):
                response=publish(rows)
                run=response["core"]["run"]
                refs=response["stored_evidence"]
                if (response.get("production_authorized") is not False or run["mode"]!="DEMO"
                    or not re.fullmatch(r"RUN-[A-F0-9]{16}",run["run_id"])
                    or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",run["incident_id"])
                    or len(refs)!=4 or len({r["evidence_id"] for r in refs})!=4
                    or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs)):
                    raise ValueError("unverified measured publication")
                receipts.append({"resource":rows[0]["resource"],"run_id":run["run_id"],
                                 "incident_id":run["incident_id"],"evidence":refs})
            if len({r["run_id"] for r in receipts})!=2:
                raise ValueError("distinct measured runs required")
            db.execute("UPDATE measured SET receipt=? WHERE tick=?",(json.dumps(receipts,sort_keys=True),expected_tick))
            return {"batch_sha256":result["batch_sha256"],"state":"PUBLISHED","incidents":receipts}
