"""Historical modeled case reports across the entire E10 campaign.

The report becomes available on the following logical tick, not on the
incident tick. No report asserts a root cause, executed fix or recovery.
"""
import json
import re
from enterprise_context import digest
from enterprise_scenarios import BY_ID, batches, root_of, VERSION

TRIAGE={
    "network":"Check path-specific loss, interface errors and site reachability; compare unaffected paths.",
    "storage":"Check capacity, I/O latency and downstream database symptoms; compare independent storage pools.",
    "identity":"Check authentication errors, identity dependencies and individual credential failures before escalation.",
    "database":"Check database-specific locks, pool usage and replica state; compare unaffected databases.",
    "compute":"Check CPU, memory and runtime health against baseline; distinguish workload pressure from host failure.",
    "application":"Check request errors, application dependency health, affected users and independent application observations.",
    "endpoint":"Verify the bound device and individual user; distinguish individual access failure from group outage.",
}
LIMIT=20

def generated(step,previous,snapshot):
    if snapshot is None: return []
    if not previous or previous["tick"]!=step["tick"]-1:
        raise ValueError("invalid case source tick")
    raw,h,receipt=snapshot
    prior_tick=previous["tick"]
    rows=json.loads(raw)
    expected=batches(previous)
    if rows!=expected or digest(rows)!=h or receipt is None:
        raise ValueError("invalid case source snapshot")
    refs=json.loads(receipt)
    if len(refs)!=len(rows) or len({r["run_id"] for r in refs})!=len(rows):
        raise ValueError("invalid case receipt count")
    result=[]
    for signals,source in zip(rows,refs):
        meta=signals[0]["enterprise"]["scenario"]
        ident=meta["scenario_id"]
        definition=BY_ID[ident]
        if (source["scenario_id"]!=ident or source["resource"]!=root_of(definition)
            or not re.fullmatch(r"RUN-[A-F0-9]{16}",source["run_id"])
            or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",source["incident_id"])
            or len(source["evidence"])!=4 or len({r["evidence_id"] for r in source["evidence"]})!=4
            or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in source["evidence"])):
            raise ValueError("invalid case receipt")
        subjects={k:v for k,v in signals[0]["enterprise"].items() if k in ("asset_id","application_id","group_id","user_id")}
        scope=sorted(set(subjects.values())|{source["resource"]})
        result.append({"id":f"ENT-CASE-{prior_tick:05d}-{ident}","version":1,"kind":"MODELED_CASE_REPORT",
            "valid_from_tick":step["tick"],"scope":scope,"subjects":subjects,
            "resource":source["resource"],"scenario_id":ident,"family":definition[1],"campaign":VERSION,
            "tenant":"synthetic-demo","title":ident.replace("_"," ").title()+" — modeled incident report",
            "text":f"{definition[10]}. {definition[11]}. Modeled {definition[6]} changed from {definition[8]} to {definition[9]} {definition[7]}. "+TRIAGE[definition[1]]+" Root cause UNKNOWN; no observed outage or recovery established; no action executed.",
            "source":{"logical_tick":prior_tick,"run_id":source["run_id"],"incident_id":source["incident_id"],"batch_sha256":h,"evidence_refs":source["evidence"]},
            "provenance":"MODEL_GENERATED_CASE_REFERENCE","observed_evidence":False,"production_authorized":False})
    return result

def store(db,rows):
    for row in rows:
        db.execute("INSERT INTO case_knowledge(doc_id,valid_from_tick,payload,payload_hash) VALUES(?,?,?,?)",
                   (row["id"],row["valid_from_tick"],json.dumps(row,sort_keys=True),digest(row)))

def read_at(db,tick,decode,scope=None,limit=LIMIT):
    if type(tick) is not int or not 0<=tick<=10000 or type(limit) is not int or not 1<=limit<=LIMIT:
        raise ValueError("invalid case knowledge read")
    result=[]
    for ident,valid,raw,h in db.execute("SELECT doc_id,valid_from_tick,payload,payload_hash FROM case_knowledge WHERE valid_from_tick<=? ORDER BY valid_from_tick DESC,doc_id",(tick,)):
        row=json.loads(raw)
        if digest(row)!=h or row["id"]!=ident or row["valid_from_tick"]!=valid:
            raise ValueError("corrupt case knowledge")
        step=decode(db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(valid,)).fetchone())
        prior=decode(db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(valid-1,)).fetchone())
        snapshot=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(valid-1,)).fetchone()
        if row not in generated(step,prior,snapshot):
            raise ValueError("case report not bound to source")
        # Require all recorded subjects, not just a shared host/app. Scope is not an authenticated ACL.
        if scope is None or set(row["scope"])<=scope:
            result.append({**row,"sha256":h})
            if len(result)>=limit: break
    return result
