"""Deterministic diagnostic challenge stream, separate from Core incident publication.

All inputs are modeled. The rule evaluator receives signals, not fixture labels.
A classification is a review recommendation, never confirmation of a real outage,
a compromise, causal attribution or permission to act.
"""
from collections import defaultdict
import json
from enterprise_context import P, ROOT, digest

VERSION="E13_TRIAGE_V1"
# source, kind, symptom, state, age_seconds; distinct source names are modeled, not authenticated.
def sig(source,kind,symptom,state="ABNORMAL",age=0):
    return (source,kind,symptom,state,age)

# case, root, app, group, user, maintenance, security, signals
CATALOG=(
 ("WAN_MONITOR_SPIKE","WAN",None,None,None,False,False,
  (sig("wan-monitor","metric","packet_loss"),)),
 ("STORAGE_CAPACITY_CORROBORATED","STORAGE-PAR",None,None,None,False,False,
  (sig("capacity-monitor","metric","capacity_used"),sig("storage-log","log","write_rejected")))),
 ("IDENTITY_SUSPICIOUS_ACCESS","IDENTITY",None,None,None,False,True,
  (sig("identity-audit","log","unusual_login_pattern"),)),
 ("PAYMENTS_DEPLOYMENT_WINDOW","ROOT","APP-PAY",None,None,True,False,
  (sig("app-monitor","metric","request_unavailable"),)),
 ("CPU_CONTRADICTORY_PROBES","LINUX-PAR",None,None,None,False,False,
  (sig("cpu-agent","metric","cpu_pressure"),sig("independent-probe","probe","cpu_pressure","NORMAL"))),
 ("HR_STALE_ERRORS","ASSET-LYO","APP-HR","GROUP-HR","USER-HR-01",False,False,
  (sig("hr-monitor","metric","http_errors",age=300),sig("hr-log","log","request_failed",age=300))),
 ("FINANCE_DUPLICATE_ALERT","PC-FIN-01","APP-PAY",None,"USER-FIN-01",False,False,
  (sig("device-agent","metric","device_error"),sig("device-agent","metric","device_error"))),
 ("CRM_NORMAL_TRAFFIC","ROOT","APP-CRM","GROUP-SALES","USER-SALES-01",False,False,
  (sig("crm-monitor","metric","request_errors","NORMAL"),sig("crm-probe","probe","request_errors","NORMAL"))),
 ("WINDOWS_TELEMETRY_GAP","WIN-LYO",None,None,None,False,False,
  (sig("host-agent","metric","memory_pressure","UNKNOWN"),)),
 ("LYON_MAINTENANCE_UNEXPECTED","STORAGE-LYO",None,None,None,True,False,
  (sig("io-monitor","metric","io_stall"),sig("db-probe","probe","transaction_unavailable"))),
 ("CRM_POOL_FAILURE","DB-CRM","APP-CRM",None,None,False,False,
  (sig("pool-monitor","metric","pool_exhaustion"),sig("sql-log","log","connection_rejected"))),
 ("NETWORK_LOG_ONLY","NET-LYO",None,None,None,False,False,
  (sig("network-log","log","link_flap"),)),
 ("SALES_ENDPOINT_SECURITY_REVIEW","PC-SALES-01","APP-CRM",None,"USER-SALES-01",False,True,
  (sig("device-audit","log","unusual_access"),sig("access-probe","probe","unexpected_session"))),
 ("PAYMENTS_MIXED_FRESHNESS","ROOT","APP-PAY",None,"USER-DIRECT-01",False,False,
  (sig("app-monitor","metric","http_errors",age=0),sig("app-log","log","request_failed",age=240))),
 ("HR_REPLICA_CORROBORATED","DB-HR","APP-HR",None,None,False,False,
  (sig("replica-monitor","metric","replica_lag"),sig("replica-log","log","replication_delayed"))),
 ("HR_ENDPOINT_NORMAL","PC-HR-01","APP-HR",None,"USER-HR-01",False,False,
  (sig("device-agent","metric","device_error","NORMAL"),)),
)
BY_ID={r[0]:r for r in CATALOG}

def evaluate(signals,maintenance_active,security_review):
    if type(maintenance_active) is not bool or type(security_review) is not bool or not isinstance(signals,list) or not 1<=len(signals)<=12:
        raise ValueError("invalid bounded triage input")
    unique={}
    for s in signals:
        if (set(s)!={"source","kind","symptom","state","age_seconds","classification"}
            or s["classification"]!="MODEL_GENERATED" or s["kind"] not in ("metric","log","probe")
            or s["state"] not in ("NORMAL","ABNORMAL","UNKNOWN")
            or type(s["age_seconds"]) is not int or not 0<=s["age_seconds"]<=3600
            or any(not isinstance(s[k],str) or not 1<=len(s[k])<=80 for k in ("source","symptom"))):
            raise ValueError("invalid modeled signal")
        unique[digest(s)]=s
    fresh=[s for s in unique.values() if s["age_seconds"]<=120 and s["state"]!="UNKNOWN"]
    abnormal=[s for s in fresh if s["state"]=="ABNORMAL"]
    symptoms=defaultdict(set)
    for s in fresh: symptoms[s["symptom"]].add(s["state"])
    contradictory=any(v=={"NORMAL","ABNORMAL"} for v in symptoms.values())
    sources=len({s["source"] for s in abnormal})
    kinds=len({s["kind"] for s in abnormal})
    corroborated=sources>=2 and kinds>=2
    if not fresh: outcome="INSUFFICIENT_FRESH_DATA"
    elif contradictory: outcome="CONTRADICTORY_SIGNALS"
    elif security_review and abnormal: outcome="SECURITY_REVIEW"
    elif corroborated: outcome="INCIDENT_CANDIDATE"
    elif maintenance_active and abnormal: outcome="MAINTENANCE_REVIEW"
    elif abnormal: outcome="UNCORROBORATED_ALERT"
    else: outcome="NOMINAL_OBSERVATION"
    return {"disposition":outcome,"input_count":len(signals),"unique_count":len(unique),
            "fresh_count":len(fresh),"abnormal_sources":sources,"abnormal_kinds":kinds,
            "contradictory":contradictory,"corroborated":corroborated,
            "root_cause":"UNKNOWN","observed_outage_established":False,
            "compromise_established":False,"automatic_incident_created":False,
            "operational_decision":"DENY","production_authorized":False}

def modeled(step):
    tick=step["tick"]
    index=((tick-1)*2)%len(CATALOG)
    output=[]
    for ident,root,app,group,user,maintenance,security,raw in CATALOG[index:index+2]:
        resource=ROOT if root=="ROOT" else P+root
        scope={"asset_id":P+("ASSET-PAR" if root=="ROOT" else root),"occurred_at":step["simulated_at"]}
        for k,v in zip(("application_id","group_id","user_id"),(app,group,user)):
            if v: scope[k]=P+v
        signals=[dict(zip(("source","kind","symptom","state","age_seconds"),r),classification="MODEL_GENERATED") for r in raw]
        output.append({"case_id":f"E13-{tick:05d}-{ident}","scenario_id":ident,"tick":tick,"resource":resource,
                       "scope":scope,"maintenance_active":maintenance,"security_review":security,
                       "signals":signals,"classification":"MODEL_GENERATED_TRIAGE_FIXTURE",
                       "assessment":evaluate(signals,maintenance,security)})
    return output

def validate_graph(rows,graph):
    from enterprise_context import normalize
    for row in rows:
        graph.validate_signal(row["resource"],normalize(row["scope"],"metric"))

def store(db,step):
    rows=modeled(step)
    db.execute("INSERT INTO triage(tick,payload,payload_hash) VALUES(?,?,?)",(step["tick"],json.dumps(rows,sort_keys=True),digest(rows)))

def read_recent(db,decode):
    records=[]
    missing=[]
    rows=db.execute("SELECT j.tick,j.step,j.step_hash,j.receipt,t.payload,t.payload_hash FROM journal j LEFT JOIN triage t ON t.tick=j.tick ORDER BY j.tick DESC LIMIT 20").fetchall()
    for r in reversed(rows):
        step=decode(r[:4])
        if r[4] is None:
            missing.append(step["tick"])
            continue
        model=json.loads(r[4])
        if model!=modeled(step) or digest(model)!=r[5]:
            raise ValueError("corrupt triage journal")
        records.extend({**row,"case_sha256":digest(row)} for row in model)
    return {"classification":"SYNTHETIC_DIAGNOSTIC_TRIAGE_E13","version":VERSION,
            "current_tick":rows[0][0] if rows else 0,"records":records,
            "unavailable_pre_e13_ticks":missing,"production_authorized":False,"operational_decision":"DENY"}
