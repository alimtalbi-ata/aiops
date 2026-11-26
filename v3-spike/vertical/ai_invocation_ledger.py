"""E23 synthetic invocation ledger in dedicated EnterpriseClock SQLite.
Only server-owned review results; no arbitrary caller receipts or public API.
Completed review persistence, not durable in-flight execution or provider attestation.
"""
from contextlib import closing
from datetime import datetime,timezone
import json
import math
import re
import uuid
from enterprise_clock import EnterpriseClock
from enterprise_context import digest
from historical_analyst_critic import assess
from dual_model_advisory import review

MAX_RECORDS=10000
FIELDS={"role","model","prompt_version","request_bytes","request_count","retry_count","cost","ttft_ms",
        "provider_identity_attested","usage_source","prompt_tokens","completion_tokens","total_tokens","latency_ms","status"}
REJECTIONS={"TRANSPORT_OR_ENVELOPE_INVALID","SCHEMA_FIELDS_INVALID","CANDIDATE_OR_CITATION_TYPE_INVALID",
            "CITATION_SET_MISMATCH","ANALYST_VERDICT_INVALID","CRITIC_SELECTION_OR_VERDICT_INVALID","ABSTAIN_WITH_SELECTION"}
TOKENS=("prompt_tokens","completion_tokens","total_tokens")
def validate_receipt(r):
    if not isinstance(r,dict) or not FIELDS<=set(r) or set(r)-FIELDS-{"rejection_code"}:
        raise ValueError("invalid receipt fields")
    if (r["role"] not in ("ANALYST","CRITIC") or r["status"] not in ("VALIDATED","REJECTED","UNAVAILABLE_OR_INVALID")
        or not isinstance(r["model"],str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}",r["model"])
        or not isinstance(r["prompt_version"],str) or not re.fullmatch(r"E[0-9]+_V[0-9]+",r["prompt_version"])
        or type(r["request_bytes"]) is not int or not 1<=r["request_bytes"]<=65536
        or type(r["request_count"]) is not int or r["request_count"]!=1
        or type(r["retry_count"]) is not int or r["retry_count"]!=0
        or r["cost"] is not None or r["ttft_ms"] is not None or r["provider_identity_attested"] is not False
        or type(r["latency_ms"]) not in (int,float) or not math.isfinite(r["latency_ms"]) or not 0<=r["latency_ms"]<=86400000
        or ("rejection_code" in r and (r["rejection_code"] not in REJECTIONS or r["status"]=="VALIDATED"))):
        raise ValueError("invalid receipt semantics")
    if r["usage_source"]=="provider_reported":
        if not all(type(r[k]) is int and 0<=r[k]<=10**9 for k in TOKENS) or r["total_tokens"]!=r["prompt_tokens"]+r["completion_tokens"]:
            raise ValueError("invalid provider usage")
    elif r["usage_source"]!="unavailable" or any(r[k] is not None for k in TOKENS):
        raise ValueError("unavailable usage must remain null")
    return dict(r)

def validate_record(r):
    if not isinstance(r,dict) or set(r)!={"classification","review_id","recorded_at","run_ids","correlation_sha256","context_sha256","state","invocations","production_authorized","operational_decision"}:
        raise ValueError("invalid record")
    if (r["classification"]!="SYNTHETIC_AI_INVOCATION_LEDGER_E23" or r["production_authorized"] is not False or r["operational_decision"]!="DENY"
        or not re.fullmatch(r"AI-[a-f0-9]{32}",r["review_id"]) or r["state"] not in ("UNKNOWN","DISPUTED","CANDIDATE_ONLY")
        or not all(isinstance(r[k],str) and re.fullmatch("[a-f0-9]{64}",r[k]) for k in ("correlation_sha256","context_sha256"))
        or not isinstance(r["run_ids"],list) or not 2<=len(r["run_ids"])<=5
        or any(not isinstance(x,str) or not re.fullmatch(r"RUN-[A-F0-9]{16}",x) for x in r["run_ids"])
        or sorted(set(r["run_ids"]))!=r["run_ids"] or not isinstance(r["invocations"],list) or len(r["invocations"])>2):
        raise ValueError("invalid record binding")
    if datetime.fromisoformat(r["recorded_at"]).utcoffset()!=timezone.utc.utcoffset(None):raise ValueError("invalid recorded time")
    calls=[validate_receipt(x) for x in r["invocations"]]
    if [x["role"] for x in calls] not in ([],["ANALYST"],["ANALYST","CRITIC"]):raise ValueError("invalid role sequence")
    if len(calls)==2 and calls[0]["status"]!="VALIDATED":raise ValueError("critic after rejected analyst")
    if r["state"]!="UNKNOWN" and (len(calls)!=2 or any(x["status"]!="VALIDATED" for x in calls)):
        raise ValueError("invalid final state")
    return r

class InvocationLedger:
    def __init__(self,root):
        self.clock=EnterpriseClock(root)
        with closing(self.clock.connect()) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS ai_invocation_reviews(review_id TEXT PRIMARY KEY,payload TEXT NOT NULL,payload_hash TEXT NOT NULL)")
    def _store(self,record):
        validate_record(record)
        raw=json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False)
        with closing(self.clock.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM ai_invocation_reviews").fetchone()[0]>=MAX_RECORDS:
                raise ValueError("ledger capacity reached")
            db.execute("INSERT INTO ai_invocation_reviews(review_id,payload,payload_hash) VALUES(?,?,?)",
                       (record["review_id"],raw,digest(record)))
    def execute(self,history,analyst_provider,critic_provider):
        baseline=assess(history)
        # No model call if the ledger is already full. Concurrent saturation
        # can still cause a post-call persistence failure: return no success.
        with closing(self.clock.connect()) as db:
            if db.execute("SELECT COUNT(*) FROM ai_invocation_reviews").fetchone()[0]>=MAX_RECORDS:
                raise ValueError("ledger capacity reached")
        out=review(history,analyst_provider,critic_provider)
        record={"classification":"SYNTHETIC_AI_INVOCATION_LEDGER_E23","review_id":"AI-"+uuid.uuid4().hex,
                "recorded_at":datetime.now(timezone.utc).isoformat(),"run_ids":sorted(baseline["analyst"]["run_ids"]),
                "correlation_sha256":baseline["analyst"]["correlation_sha256"],"context_sha256":out["context_sha256"],
                "state":out["state"],"invocations":out["invocations"],"production_authorized":False,"operational_decision":"DENY"}
        self._store(record)
        return {"review_id":record["review_id"],"receipt_sha256":digest(record),"assessment":out}
    def read(self,review_id):
        if not isinstance(review_id,str) or not re.fullmatch(r"AI-[a-f0-9]{32}",review_id):raise ValueError("invalid review id")
        with closing(self.clock.connect()) as db:
            row=db.execute("SELECT payload,payload_hash FROM ai_invocation_reviews WHERE review_id=?",(review_id,)).fetchone()
        if row is None:raise KeyError("review unavailable")
        record=json.loads(row[0])
        if record["review_id"]!=review_id or digest(record)!=row[1]:raise ValueError("corrupt invocation receipt")
        validate_record(record)
        return {"record":record,"receipt_sha256":row[1]}
    def summary(self,review_ids):
        if not isinstance(review_ids,list) or not 1<=len(review_ids)<=100 or len(set(review_ids))!=len(review_ids):
            raise ValueError("bounded distinct review IDs required")
        records=[self.read(i)["record"] for i in review_ids]
        calls=[c for r in records for c in r["invocations"]]
        groups=[]
        for role,model,prompt in sorted({(x["role"],x["model"],x["prompt_version"]) for x in calls}):
            subset=[x for x in calls if (x["role"],x["model"],x["prompt_version"])==(role,model,prompt)]
            reported=[x for x in subset if x["usage_source"]=="provider_reported"]
            latencies=sorted(x["latency_ms"] for x in subset)
            groups.append({"role":role,"model":model,"prompt_version":prompt,"invocations":len(subset),
                "validated":sum(x["status"]=="VALIDATED" for x in subset),"usage_reported_count":len(reported),
                "latency_p50_ms":latencies[math.ceil(.5*len(latencies))-1],
                "latency_p95_ms":latencies[math.ceil(.95*len(latencies))-1],
                "reported_partial_total_tokens":sum(x["total_tokens"] for x in reported) if reported else None,
                **{k:sum(x[k] for x in reported) if len(reported)==len(subset) else None for k in TOKENS},
                "cost":None,"ttft_ms":None})
        return {"classification":"SYNTHETIC_AI_INVOCATION_AGGREGATE_E23","reviews":len(records),
                "invocations":len(calls),"groups":groups,"production_authorized":False,"operational_decision":"DENY"}
