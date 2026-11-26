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
        import threading
        self.clock=clock
        self.lock=threading.Lock()
        super().__init__()

    def _prepare_storage(self):
        # Read-only GAMMA routes must not initialize HITL storage.
        from contextlib import closing
        with closing(self.clock.connect()) as db, db:
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

    @staticmethod
    def action_scope(scope):
        import re
        if scope is None:
            return None
        if (not isinstance(scope,dict) or set(scope)!={"action","resource","target_id"}
            or scope["action"]!="RESET_LAB_HTTP_DELAY"
            or not isinstance(scope["resource"],str) or not re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}",scope["resource"])
            or not isinstance(scope["target_id"],str) or not re.fullmatch(r"[a-f0-9]{32}",scope["target_id"])):
            raise ValueError("invalid confined lab action scope")
        return dict(scope)

    def request(self, incident, run, evidence, *, lab_action=None):
        binding=self.binding(incident,run,evidence)
        scope=self.action_scope(lab_action)
        with self.lock:
            now=time.monotonic()
            self.pending={k:v for k,v in self.pending.items() if v[1]>=now}
            if len(self.pending)>=100:
                raise ValueError("Demo queue full")
            self._prepare_storage()
            key=secrets.token_urlsafe(24)
            self.pending[key]=(binding,time.monotonic()+300,incident,run,scope)
        return {"request_id":key,"decision":"HUMAN_APPROVAL","operational_decision":"DENY"}

    @staticmethod
    def _hash(record):
        return hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",",":")).encode()).hexdigest()

    def decide(self,key,incident,run,evidence,approved,*,lab_action=None):
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
                scope=self.action_scope(lab_action)
            except ValueError:
                current=None
                scope=None
            valid=(entry[1]>=time.monotonic() and current is not None
                   and secrets.compare_digest(entry[0],current) and scope==entry[4])
            decision="SIMULATE_ONLY" if valid and approved is True else "DENY"
            record={"classification":"SYNTHETIC_HITL_DECISION_RECEIPT",
                    "receipt_id":"HITL-"+uuid.uuid4().hex,"incident_id":entry[2],
                    "run_id":entry[3],"context_sha256":entry[0],
                    "evaluated_context_sha256":current,
                    "recorded_at":datetime.now(timezone.utc).isoformat(),
                    "decision":decision,"operational_decision":"DENY",
                    "executed_on_host":False,"production_authorized":False}
            if entry[4] is not None:
                record["lab_action"]=entry[4]
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
            return self._read_receipt(db,receipt_id)

    def _read_receipt(self,db,receipt_id):
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


    def reserve_lab_action(self,receipt_id,receipt_sha256,incident,run,evidence,
                           lab_action,workflow_id,policy_port):
        """Internal pre-execution reservation only, no action and no capability.

        Caller must supply a server-owned, freshly verified context and target.
        Not exposed to HTTP or registered in Temporal. Restoring an older DB is
        not an execution fence; no execution is allowed by this method.
        """
        from contextlib import closing
        from datetime import datetime,timezone
        import re
        from policy_demo import simulation_decision
        scope=self.action_scope(lab_action)
        context=self.binding(incident,run,evidence)
        if (scope is None or not re.fullmatch(r"RUN-[A-F0-9]{16}",run)
            or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",incident)
            or workflow_id!=run or not isinstance(receipt_id,str)
            or not re.fullmatch(r"HITL-[a-f0-9]{32}",receipt_id)
            or not isinstance(receipt_sha256,str) or not re.fullmatch(r"[a-f0-9]{64}",receipt_sha256)):
            raise ValueError("invalid reservation binding")
        # No caller-supplied policy result; recheck the existing lab adapter.
        policy=simulation_decision(policy_port,len(evidence))
        if policy!={"policy_decision":"SIMULATE","simulation_only":True,
                    "operational_decision":"DENY","executed_on_host":False,
                    "production_authorized":False}:
            raise ValueError("simulation policy required")
        with closing(self.clock.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            receipt=self._read_receipt(db,receipt_id)
            record=receipt["record"]
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(record["recorded_at"])).total_seconds()
            if (not secrets.compare_digest(receipt["receipt_sha256"],receipt_sha256)
                or record["decision"]!="SIMULATE_ONLY" or record.get("lab_action")!=scope
                or record["run_id"]!=run or record["incident_id"]!=incident
                or record["context_sha256"]!=context or record["evaluated_context_sha256"]!=context
                or not 0<=age<=300):
                raise ValueError("receipt not admissible")
            db.execute("""CREATE TABLE IF NOT EXISTS hitl_lab_reservations
                       (run_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL UNIQUE,
                        target_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, payload_hash TEXT NOT NULL)""")
            old=db.execute("SELECT payload,payload_hash FROM hitl_lab_reservations WHERE run_id=? OR receipt_id=? OR target_id=?",
                           (run,receipt_id,scope["target_id"])).fetchall()
            binding={"run_id":run,"incident_id":incident,"workflow_id":workflow_id,
                     "receipt_id":receipt_id,"receipt_sha256":receipt_sha256,
                     "context_sha256":context,"lab_action":scope}
            if old:
                if len(old)!=1:
                    raise ValueError("conflicting reservation")
                prior=json.loads(old[0][0])
                if self._hash(prior)!=old[0][1] or prior.get("binding")!=binding:
                    raise ValueError("conflicting reservation")
                return {**prior,"reservation_sha256":old[0][1],"disposition":"ALREADY_RESERVED_BLOCKED"}
            result={"classification":"SYNTHETIC_LAB_RESERVATION",
                    "binding":binding,"operational_decision":"DENY",
                    "executed_on_host":False,"production_authorized":False,
                    "action_authorized":False}
            digest=self._hash(result)
            db.execute("INSERT INTO hitl_lab_reservations VALUES (?,?,?,?,?)",
                       (run,receipt_id,scope["target_id"],json.dumps(result,sort_keys=True),digest))
        return {**result,"reservation_sha256":digest,"disposition":"RESERVED_NO_EXECUTION"}
