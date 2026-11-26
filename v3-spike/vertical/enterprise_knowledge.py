"""Synthetic lifecycle knowledge, separate from observed Evidence and runbooks."""
import json
import re
from enterprise_context import P, digest

SCOPE=[P+"ASSET-PAR",P+"APP-PAY"]
LIMIT=20

def generated(step, previous):
    tick=step["tick"]
    def doc(kind, title, body, source):
        return {"id":f"ENT-KNOW-{tick:05d}-{kind}","version":1,"kind":kind,
                "valid_from_tick":tick,"scope":list(SCOPE),"tenant":"synthetic-demo",
                "title":title,"text":body,"source":source,
                "provenance":"MODEL_GENERATED_LIFECYCLE_REFERENCE","observed_evidence":False,
                "production_authorized":False}
    if step["phase"]=="CHANGE":
        return [doc("CHANGE","Synthetic Payments change record",
                    "Scheduled modeled configuration change. Compare baseline latency and user context; change is not proof of cause.",
                    {"logical_tick":tick,"run_id":None,"incident_id":None,"evidence_refs":[]})]
    if step["phase"]!="MODEL_RECOVERY":
        return []
    if not previous or previous["tick"]!=tick-1 or previous["phase"]!="DEGRADED":
        raise ValueError("missing prior degradation")
    receipt=previous["publication"]
    if not receipt or receipt["state"]!="PUBLISHED" or len(receipt["evidence"])!=4:
        raise ValueError("prior incident publication not confirmed")
    if not re.fullmatch(r"RUN-[A-F0-9]{16}",receipt["run_id"]) or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",receipt["incident_id"]):
        raise ValueError("invalid source binding")
    refs=receipt["evidence"]
    if len({r["evidence_id"] for r in refs})!=4 or any(not re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs):
        raise ValueError("invalid source evidence refs")
    source={"logical_tick":tick-1,"run_id":receipt["run_id"],"incident_id":receipt["incident_id"],"evidence_refs":refs}
    return [
        doc("INCIDENT","Synthetic Payments incident report",
            f"Modeled latency {previous['modeled_latency_ms']} ms against baseline {previous['baseline_ms']} ms. Published DEMO incident; root cause unknown. Source references are model-generated signals, not real outage evidence.",source),
        doc("RECOVERY","Synthetic Payments recovery note",
            f"Model returned to {step['modeled_latency_ms']} ms. No remediation was executed, no measured recovery established. Verify fresh observations before any resolution claim.",source),
    ]

def store(db, rows):
    for row in rows:
        db.execute("INSERT INTO knowledge(doc_id,valid_from_tick,payload,payload_hash) VALUES(?,?,?,?)",
                   (row["id"],row["valid_from_tick"],json.dumps(row,sort_keys=True),digest(row)))

def read_at(db,tick,decode,scope=None):
    """Bounded output; scan only immutable records at or before the logical tick."""
    if type(tick) is not int or not 0<=tick<=10000:
        raise ValueError("invalid knowledge tick")
    rows=db.execute("SELECT doc_id,valid_from_tick,payload,payload_hash FROM knowledge WHERE valid_from_tick<=? ORDER BY valid_from_tick DESC,doc_id",(tick,))
    result=[]
    for ident,valid,raw,h in rows:
        row=json.loads(raw)
        if digest(row)!=h or row["id"]!=ident or row["valid_from_tick"]!=valid:
            raise ValueError("corrupt knowledge document")
        step=decode(db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(valid,)).fetchone())
        prior=db.execute("SELECT tick,step,step_hash,receipt FROM journal WHERE tick=?",(valid-1,)).fetchone()
        if row not in generated(step,decode(prior) if prior else None):
            raise ValueError("knowledge source does not match world")
        if scope is None or set(row["scope"]) & scope:
            result.append({**row,"sha256":h})
            if len(result)>=LIMIT:
                break
    return result

def rank(rows,query,limit=5):
    if not isinstance(query,str) or len(query)>512 or type(limit) is not int or not 1<=limit<=5:
        raise ValueError("invalid knowledge query")
    tokens=lambda x:set(re.findall(r"[a-z0-9]{2,40}",x.lower()))
    words=tokens(query)
    ranked=[{**r,"lexical_score":len(words&tokens(r["title"]+" "+r["text"]))} for r in rows]
    return sorted(ranked,key=lambda r:(-r["lexical_score"],-r["valid_from_tick"],r["id"]))[:limit]
