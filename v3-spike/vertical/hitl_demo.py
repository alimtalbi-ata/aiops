"""In-memory demo approval gate; never authorizes host execution."""
import hashlib
import json
import secrets
import time

class ApprovalGate:
    def __init__(self):
        self.pending={}
    @staticmethod
    def binding(incident,run,evidence):
        if not incident or not run or not evidence:
            raise ValueError("Missing context")
        return hashlib.sha256(json.dumps([incident,run,evidence],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    def request(self,incident,run,evidence):
        if len(self.pending)>=100:
            raise ValueError("Demo queue full")
        key=secrets.token_urlsafe(24)
        self.pending[key]=(self.binding(incident,run,evidence),time.monotonic()+300)
        return {"request_id":key,"decision":"HUMAN_APPROVAL","operational_decision":"DENY"}
    def decide(self,key,incident,run,evidence,approved):
        entry=self.pending.pop(key,None)
        valid=entry is not None and entry[1]>=time.monotonic() and secrets.compare_digest(entry[0],self.binding(incident,run,evidence))
        return {"decision":"SIMULATE_ONLY" if valid and approved is True else "DENY",
                "classification":"SYNTHETIC_HITL_DEMO","operational_decision":"DENY",
                "executed_on_host":False,"production_authorized":False}


class DurableApprovalGate(ApprovalGate):
    """Audit completed synthetic decisions in the existing private world database.

    Pending requests deliberately expire on process restart. A receipt is audit
    evidence, NOT a capability, an execution lease or permission for a Worker.
    No raw request token, prompts or external target is persisted.
    """
    def __init__(self, clock):
        from contextlib import closing
        import threading
        self.clock=clock
        self.lock=threading.Lock()
        super().__init__()
        with closing(clock.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS hitl_decision_receipts (receipt_id TEXT PRIMARY KEY, payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")

    @staticmethod
    def binding(incident, run, evidence):
        import re
        from evidence_retrieval import index_references
        if not isinstance(incident,str) or not re.fullmatch(r"INC-CI-[A-Za-z0-9-]{1,96}",incident):
            raise ValueError("synthetic incident required")
        if not isinstance(run,str) or not re.fullmatch(r"RUN-(?:CI-[A-Z0-9-]{1,80}|[A-F0-9]{16})",run):
            raise ValueError("synthetic run required")
        refs=index_references(evidence)
        return ApprovalGate.binding(incident,run,[refs[k] for k in sorted(refs)])

    def request(self, incident, run, evidence):
        binding=self.binding(incident,run,evidence)
        with self.lock:
            now=time.monotonic()
            self.pending={k:v for k,v in self.pending.items() if v[1]>=now}
            if len(self.pending)>=100:
                raise ValueError("Demo queue full")
            key=secrets.token_urlsafe(24)
            self.pending[key]=(binding,now+300,incident,run)
        return {"request_id":key,"decision":"HUMAN_APPROVAL","operational_decision":"DENY"}

    @staticmethod
    def _hash(record):
        return hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",",":")).encode()).hexdigest()

    def decide(self,key,incident,run,evidence,approved):
        from contextlib import closing
        from datetime import datetime,timezone
        import uuid
        result={"decision":"DENY","classification":"SYNTHETIC_HITL_DEMO",
                "operational_decision":"DENY","executed_on_host":False,"production_authorized":False}
        with self.lock:
            entry=self.pending.pop(key,None) if isinstance(key,str) else None
            if entry is None:
                return result
            try:
                current=self.binding(incident,run,evidence)
            except ValueError:
                current=None
            valid=(entry[1]>=time.monotonic() and current is not None
                   and secrets.compare_digest(entry[0],current))
            decision="SIMULATE_ONLY" if valid and approved is True else "DENY"
            record={"classification":"SYNTHETIC_HITL_DECISION_RECEIPT",
                    "receipt_id":"HITL-"+uuid.uuid4().hex,"incident_id":entry[2],
                    "run_id":entry[3],"context_sha256":entry[0],
                    "evaluated_context_sha256":current,
                    "recorded_at":datetime.now(timezone.utc).isoformat(),
                    "decision":decision,"operational_decision":"DENY",
                    "executed_on_host":False,"production_authorized":False}
            digest=self._hash(record)
            with closing(self.clock.connect()) as db,db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT COUNT(*) FROM hitl_decision_receipts").fetchone()[0]>=10000:
                    raise ValueError("HITL receipt capacity exhausted")
                db.execute("INSERT INTO hitl_decision_receipts VALUES (?,?,?)",
                           (record["receipt_id"],json.dumps(record,sort_keys=True),digest))
            # Return the simulation label only after commit; the receipt cannot execute anything.
            result.update(decision=decision,receipt_id=record["receipt_id"],receipt_sha256=digest)
            return result

    def read_receipt(self,receipt_id):
        """Internal audit read only; never authorize an action from this method."""
        from contextlib import closing
        with closing(self.clock.connect()) as db:
            row=db.execute("SELECT payload,payload_hash FROM hitl_decision_receipts WHERE receipt_id=?",
                           (receipt_id,)).fetchone()
        if row is None:
            raise ValueError("unknown HITL receipt")
        record=json.loads(row[0])
        if (record.get("receipt_id")!=receipt_id or self._hash(record)!=row[1]
            or record.get("classification")!="SYNTHETIC_HITL_DECISION_RECEIPT"
            or record.get("operational_decision")!="DENY" or record.get("executed_on_host") is not False
            or record.get("production_authorized") is not False
            or record.get("decision") not in ("DENY","SIMULATE_ONLY")):
            raise ValueError("invalid HITL receipt")
        return {"record":record,"receipt_sha256":row[1]}
