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
from enterprise_activity import activity_for, decode_activity
import enterprise_corpus as corpus
import enterprise_knowledge as knowledge
import enterprise_hybrid as hybrid
import enterprise_case_knowledge as cases
import enterprise_episodes as episodes
import enterprise_triage as triage
import enterprise_parametric as parametric

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
            db.execute("CREATE TABLE IF NOT EXISTS technical(tick INTEGER PRIMARY KEY REFERENCES journal(tick), batches TEXT NOT NULL, batch_hash TEXT NOT NULL, receipt TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS scenarios(tick INTEGER PRIMARY KEY REFERENCES journal(tick), batches TEXT NOT NULL, batch_hash TEXT NOT NULL, receipt TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS activity(tick INTEGER PRIMARY KEY REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS corpus(doc_id TEXT NOT NULL, version INTEGER NOT NULL, valid_from_tick INTEGER NOT NULL REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL, PRIMARY KEY(doc_id,version))")
            db.execute("CREATE TABLE IF NOT EXISTS knowledge(doc_id TEXT PRIMARY KEY, valid_from_tick INTEGER NOT NULL REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS case_knowledge(doc_id TEXT PRIMARY KEY, valid_from_tick INTEGER NOT NULL REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS episodes(tick INTEGER PRIMARY KEY REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS triage(tick INTEGER PRIMARY KEY REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS parametric_profile(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS parametric_ticks(tick INTEGER PRIMARY KEY REFERENCES journal(tick), payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
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
                technical=db.execute("SELECT batches,batch_hash,receipt FROM technical WHERE tick=?",(item["tick"],)).fetchone()
                if technical is not None:
                    item["technical_capture"]=self.decode_capture(technical)
                campaign=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(item["tick"],)).fetchone()
                if campaign is not None:
                    item["scenario_capture"]=self.decode_capture(campaign)
        latest=recent[-1] if recent else None
        return {"classification":"SYNTHETIC_ENTERPRISE_CLOCK_E2","world_id":WORLD,
                "current_tick":latest["tick"] if latest else 0,"pending":bool(latest and latest["publication"] is None),
                "latest":latest,"recent":recent,"clock_mode":"MANUAL_LOGICAL_TIME","production_authorized":False,"operational_decision":"DENY"}
    def activity(self):
        """Read bounded recent activity; never fabricate activity for pre-E6 ticks."""
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            rows=db.execute("SELECT j.tick,j.step,j.step_hash,j.receipt,a.payload,a.payload_hash FROM journal j LEFT JOIN activity a ON a.tick=j.tick ORDER BY j.tick DESC LIMIT 20").fetchall()
            missing=[]
            timeline=[]
            for row in reversed(rows):
                step=self.decode(row[:4])
                if row[4] is None:
                    missing.append(step["tick"])
                else:
                    timeline.extend(decode_activity(step,row[4],row[5]))
        return {"classification":"SYNTHETIC_ACTIVITY_JOURNAL_E6","world_id":WORLD,
                "current_tick":rows[0][0] if rows else 0,"unavailable_pre_e6_ticks":missing,
                "records":timeline,"operational_decision":"DENY","production_authorized":False}

    def document_catalog(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            tick=db.execute("SELECT COALESCE(MAX(tick),0) FROM journal").fetchone()[0]
            rows=corpus.catalog_at(db,tick) if tick else []
        return {"classification":"SYNTHETIC_VERSIONED_CORPUS_E7","current_tick":tick,
                "documents":[{**r,"sha256":digest(r)} for r in rows],
                "production_authorized":False,"operational_decision":"DENY"}

    def knowledge_catalog(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            tick=db.execute("SELECT COALESCE(MAX(tick),0) FROM journal").fetchone()[0]
            rows=knowledge.read_at(db,tick,self.decode)
        return {"classification":"SYNTHETIC_LIFECYCLE_KNOWLEDGE_E8","current_tick":tick,
                "documents":rows,"limit":knowledge.LIMIT,"production_authorized":False,"operational_decision":"DENY"}

    def configure_parametric(self,value,graph):
        # Validate all planned resources and populations before committing config.
        parametric.validate_graph(parametric.plan(value),graph)
        with closing(self.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            parametric.configure(db,value)
            return parametric.timeline(db,self.decode)

    def parametric_timeline(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            return parametric.timeline(db,self.decode)

    def triage_timeline(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            return triage.read_recent(db,self.decode)

    def episode_timeline(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            return episodes.read_recent(db,self.decode)

    def case_catalog(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            tick=db.execute("SELECT COALESCE(MAX(tick),0) FROM journal").fetchone()[0]
            rows=cases.read_at(db,tick,self.decode)
            count=db.execute("SELECT COUNT(*) FROM case_knowledge WHERE valid_from_tick<=?",(tick,)).fetchone()[0]
        return {"classification":"SYNTHETIC_DIVERSE_CASE_KNOWLEDGE_E11","current_tick":tick,"documents":rows,
                "total_documents":count,"limit":cases.LIMIT,"production_authorized":False,"operational_decision":"DENY"}

    def historical_documents(self, run_id, scope, query):
        if not re.fullmatch(r"RUN-[A-F0-9]{16}",run_id):
            raise ValueError("invalid run identity")
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            ticks=set()
            for tick,raw in db.execute("SELECT tick,receipt FROM journal WHERE receipt IS NOT NULL"):
                receipt=json.loads(raw)
                if receipt.get("run_id")==run_id: ticks.add(tick)
            for table in ("measured","technical","scenarios"):
                for tick,raw in db.execute("SELECT tick,receipt FROM "+table+" WHERE receipt IS NOT NULL"):
                    if any(r["run_id"]==run_id for r in json.loads(raw)): ticks.add(tick)
            if not ticks:
                return {"state":"UNBOUND_LEGACY","logical_tick":None,"citations":[]}
            if len(ticks)!=1: raise ValueError("ambiguous run tick")
            tick=ticks.pop()
            rows=corpus.catalog_at(db,tick)
            if not rows:
                return {"state":"PRE_E7_UNAVAILABLE","logical_tick":tick,"citations":[]}
            lifecycle=knowledge.read_at(db,tick,self.decode,scope)
            reports=cases.read_at(db,tick,self.decode,scope,limit=10)
            # Keep candidate budget bounded and legacy runbook/lifecycle ranking stable.
            case_retrieval=hybrid.retrieve(reports,scope,query or " ",tick)
            return {"state":"HISTORICAL_LOGICAL_VERSION","logical_tick":tick,
                    "catalog_sha256":digest(rows),"citations":corpus.references(rows,scope,query),
                    "lifecycle_citations":knowledge.rank(lifecycle,query),
                    "hybrid_retrieval":hybrid.retrieve(rows+lifecycle,scope,query or " ",tick),
                    "case_retrieval":case_retrieval}

    def advance(self, expected_tick, publish):
        if type(expected_tick) is not int or not 1<=expected_tick<=MAX_TICK:
            raise ValueError("invalid expected tick")
        # Durable outbox: record the deterministic step before remote writes.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT tick,receipt FROM journal ORDER BY tick DESC LIMIT 1").fetchone()
            last=latest[0] if latest else 0
            if expected_tick==last+1 and (db.execute("SELECT 1 FROM measured WHERE receipt IS NULL LIMIT 1").fetchone() or db.execute("SELECT 1 FROM technical WHERE receipt IS NULL LIMIT 1").fetchone() or db.execute("SELECT 1 FROM scenarios WHERE receipt IS NULL LIMIT 1").fetchone()):
                raise ValueError("pending measurement publication must be retried")
            if expected_tick==last+1 and (latest is None or latest[1] is not None):
                step=model(expected_tick)
                db.execute("INSERT INTO journal(tick,step,step_hash) VALUES(?,?,?)",(expected_tick,json.dumps(step,sort_keys=True),digest(step)))
                records=activity_for(step)
                db.execute("INSERT INTO activity(tick,payload,payload_hash) VALUES(?,?,?)",(expected_tick,json.dumps(records,sort_keys=True),digest(records)))
                previous=corpus.catalog_at(db,expected_tick)
                corpus.store(db,corpus.change_rows(expected_tick,previous) if previous else corpus.initial_rows(expected_tick))
                prior=db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(expected_tick-1,)).fetchone()
                knowledge.store(db,knowledge.generated(step,self.decode(prior) if prior else None))
                snapshot=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(expected_tick-1,)).fetchone()
                cases.store(db,cases.generated(step,self.decode(prior) if prior else None,snapshot))
                episodes.store(db,step)
                triage.store(db,step)
                parametric.store(db,step)
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

    def capture_technical(self, expected_tick, collect, publish):
        """Durable isolated workload measurements associated with a committed logical tick."""
        if type(expected_tick) is not int or not 1<=expected_tick<=MAX_TICK:
            raise ValueError("invalid technical tick")
        from enterprise_context import P, validate_telemetry
        from ingestion_demo import ingest
        expected={P+x for x in ("LINUX-PAR","STORAGE-PAR","DB-PAY","NET-PAR")}
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT tick,step,step_hash,receipt FROM journal ORDER BY tick DESC LIMIT 1").fetchone()
            if latest is None or latest[0]!=expected_tick or self.decode(latest)["publication"] is None:
                raise ValueError("current committed tick required")
            row=db.execute("SELECT batches,batch_hash,receipt FROM technical WHERE tick=?",(expected_tick,)).fetchone()
            if row is None:
                batches=collect()
                if not isinstance(batches,list) or len(batches)!=4:
                    raise ValueError("four technical workloads required")
                roots=set()
                for rows in batches:
                    normalized=ingest(rows)["incidents"]
                    if len(rows)!=3 or len(normalized)!=1 or len(normalized[0]["evidence"])!=3:
                        raise ValueError("invalid technical batch")
                    roots.add(normalized[0]["resource"])
                    metrics=[validate_telemetry(r["enterprise"]["telemetry"])["metric"] for r in rows if r["kind"]=="metric"]
                    if len(set(metrics))!=2 or sum(r["kind"]=="event" for r in rows)!=1:
                        raise ValueError("two distinct technical metrics and event required")
                if roots!=expected:
                    raise ValueError("unexpected technical resources")
                db.execute("INSERT INTO technical(tick,batches,batch_hash) VALUES(?,?,?)",
                           (expected_tick,json.dumps(batches,sort_keys=True),digest(batches)))
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT batches,batch_hash,receipt FROM technical WHERE tick=?",(expected_tick,)).fetchone()
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
                    or len(refs)!=3 or len({r["evidence_id"] for r in refs})!=3
                    or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs)):
                    raise ValueError("unverified technical publication")
                receipts.append({"resource":rows[0]["resource"],"run_id":run["run_id"],
                                 "incident_id":run["incident_id"],"evidence":refs})
            if len({r["run_id"] for r in receipts})!=4:
                raise ValueError("distinct technical runs required")
            db.execute("UPDATE technical SET receipt=? WHERE tick=?",(json.dumps(receipts,sort_keys=True),expected_tick))
            return {"batch_sha256":result["batch_sha256"],"state":"PUBLISHED","incidents":receipts}

    def capture_scenarios(self, expected_tick, publish):
        """Explicit campaign, orthogonal to nominal activity and actual measured workloads."""
        from enterprise_scenarios import batches
        if type(expected_tick) is not int or not 1<=expected_tick<=MAX_TICK:
            raise ValueError("invalid campaign tick")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute("SELECT tick,step,step_hash,receipt FROM journal ORDER BY tick DESC LIMIT 1").fetchone()
            if latest is None or latest[0]!=expected_tick or self.decode(latest)["publication"] is None:
                raise ValueError("current committed tick required")
            expected=batches(model(expected_tick))
            row=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(expected_tick,)).fetchone()
            if row is None:
                db.execute("INSERT INTO scenarios(tick,batches,batch_hash) VALUES(?,?,?)",
                           (expected_tick,json.dumps(expected,sort_keys=True),digest(expected)))
            elif json.loads(row[0])!=expected or row[1]!=digest(expected):
                raise ValueError("campaign snapshot mismatch")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(expected_tick,)).fetchone()
            result=self.decode_capture(row)
            if json.loads(row[0])!=expected:
                raise ValueError("campaign snapshot mismatch")
            if result["state"]=="PUBLISHED":
                return result
            receipts=[]
            for rows in expected:
                response=publish(rows)
                run=response["core"]["run"]
                refs=response["stored_evidence"]
                if (response.get("production_authorized") is not False or run["mode"]!="DEMO"
                    or not re.fullmatch(r"RUN-[A-F0-9]{16}",run["run_id"])
                    or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",run["incident_id"])
                    or len(refs)!=4 or len({r["evidence_id"] for r in refs})!=4
                    or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs)):
                    raise ValueError("unverified scenario publication")
                receipts.append({"resource":rows[0]["resource"],"scenario_id":rows[0]["enterprise"]["scenario"]["scenario_id"],
                                 "run_id":run["run_id"],"incident_id":run["incident_id"],"evidence":refs})
            if len({r["run_id"] for r in receipts})!=2:
                raise ValueError("distinct scenario runs required")
            db.execute("UPDATE scenarios SET receipt=? WHERE tick=?",(json.dumps(receipts,sort_keys=True),expected_tick))
            return {"batch_sha256":result["batch_sha256"],"state":"PUBLISHED","incidents":receipts}
