"""Deterministic multi-tick modeled episodes; topology hypotheses are not RCA."""
import json
import re
from enterprise_context import P, digest
from enterprise_scenarios import batches

VERSION="E12_EPISODES_V1"
# Edges are actual dependency directions (dependent -> dependency).
DEFINITIONS={
    "STORAGE_CASCADE": {
        "type":"CASCADE_HYPOTHESIS","resources":["STORAGE-PAR","DB-PAY","DB-CRM","APP-PAY","APP-CRM"],
        "edges":[("DB-PAY","STORAGE-PAR","requires"),("DB-CRM","STORAGE-PAR","requires"),("APP-PAY","DB-PAY","requires"),("APP-CRM","DB-CRM","requires")],
        "stages":[
            ("ONSET",[("STORAGE-PAR","capacity_used","percent",98)],["DISK_FULL"]),
            ("PROPAGATION",[("DB-PAY","lock_wait_ms","ms",2500),("DB-CRM","io_wait_ms","ms",700)],["DB_LOCK"]),
            ("PROPAGATION",[("APP-PAY","http_error_rate","percent",35),("APP-CRM","request_timeout_rate","percent",48)],[]),
            ("PARTIAL_RECOVERY",[("STORAGE-PAR","capacity_used","percent",72),("APP-CRM","request_timeout_rate","percent",48)],["CRM_TIMEOUT"]),
            ("PARTIAL_RECOVERY",[("APP-PAY","http_error_rate","percent",1),("APP-CRM","request_timeout_rate","percent",22)],[]),
            ("RECURRENCE",[("DB-CRM","connection_pool_used","percent",100)],["DB_POOL_EXHAUSTION"]),
            ("MODEL_RECOVERY",[("DB-CRM","connection_pool_used","percent",30),("APP-CRM","request_timeout_rate","percent",0.2)],[]),
            ("MODEL_STABLE",[("STORAGE-PAR","capacity_used","percent",63)],[])]},
    "SHARED_IDENTITY": {
        "type":"SHARED_DEPENDENCY_HYPOTHESIS","resources":["IDENTITY","APP-PAY","APP-CRM","APP-HR"],
        "edges":[("APP-PAY","IDENTITY","requires"),("APP-CRM","IDENTITY","requires"),("APP-HR","IDENTITY","requires")],
        "stages":[
            ("BASELINE",[("IDENTITY","auth_failure_rate","percent",1)],[]),
            ("ONSET",[("IDENTITY","auth_failure_rate","percent",72)],["AUTH_FAILURE"]),
            ("PROPAGATION",[("APP-HR","http_error_rate","percent",45),("APP-PAY","auth_failure_rate","percent",40)],["HR_HTTP_ERRORS"]),
            ("PARTIAL_RECOVERY",[("APP-HR","http_error_rate","percent",12),("APP-PAY","auth_failure_rate","percent",2)],[]),
            ("MODEL_RECOVERY",[("IDENTITY","auth_failure_rate","percent",1)],[]),
            ("MODEL_STABLE",[("APP-HR","http_error_rate","percent",0.5)],[]),
            ("MODEL_STABLE",[("IDENTITY","auth_failure_rate","percent",1)],[]),
            ("MODEL_STABLE",[("IDENTITY","auth_failure_rate","percent",1)],[])]},
    "LYON_INTERMITTENT": {
        "type":"INTERMITTENT","resources":["NET-LYO","WIN-LYO","ASSET-LYO","APP-HR"],
        "edges":[("WIN-LYO","NET-LYO","requires"),("ASSET-LYO","WIN-LYO","requires"),("APP-HR","ASSET-LYO","depends_on")],
        "stages":[
            ("BASELINE",[("NET-LYO","packet_loss","percent",0)],[]),
            ("ONSET",[("NET-LYO","packet_loss","percent",20)],[]),
            ("MODEL_RECOVERY",[("NET-LYO","packet_loss","percent",0)],[]),
            ("RECURRENCE",[("NET-LYO","packet_loss","percent",25)],[]),
            ("MODEL_RECOVERY",[("NET-LYO","packet_loss","percent",0)],[]),
            ("RECURRENCE",[("NET-LYO","packet_loss","percent",65)],["LOCAL_NETWORK_LOSS"]),
            ("PARTIAL_RECOVERY",[("NET-LYO","packet_loss","percent",5)],[]),
            ("MODEL_RECOVERY",[("NET-LYO","packet_loss","percent",0)],[])]},
    "INDIVIDUAL_FINANCE": {
        "type":"INDEPENDENT_INDIVIDUAL","resources":["PC-FIN-01","USER-FIN-01"],
        "edges":[("USER-FIN-01","PC-FIN-01","uses_device")],
        "stages":[
            ("BASELINE",[("PC-FIN-01","device_error_count","count",0)],[]),
            ("BASELINE",[("PC-FIN-01","device_error_count","count",0)],[]),
            ("BASELINE",[("PC-FIN-01","device_error_count","count",0)],[]),
            ("ONSET",[("PC-FIN-01","device_error_count","count",12)],["FIN_DEVICE_FAILURE"]),
            ("PARTIAL_RECOVERY",[("PC-FIN-01","device_error_count","count",3)],[]),
            ("MODEL_RECOVERY",[("PC-FIN-01","device_error_count","count",0)],[]),
            ("MODEL_STABLE",[("PC-FIN-01","device_error_count","count",0)],[]),
            ("MODEL_STABLE",[("PC-FIN-01","device_error_count","count",0)],[])]},
}

def modeled(step):
    tick=step["tick"]
    cycle=(tick-1)//8+1
    index=(tick-1)%8
    rows=[]
    for name,d in DEFINITIONS.items():
        phase,signals,links=d["stages"][index]
        rows.append({"episode_id":f"E12-{cycle:04d}-{name}","episode_type":d["type"],
                     "scenario":name,"tick":tick,"occurred_at":step["simulated_at"],"phase":phase,
                     "resources":[P+x for x in d["resources"]],
                     "dependency_edges":[[P+a,P+b,r] for a,b,r in d["edges"]],
                     "observations":[{"resource":P+r,"metric":m,"unit":u,"value":v,"classification":"MODEL_GENERATED"} for r,m,u,v in signals],
                     "candidate_scenario_ids":links,"classification":"MODEL_GENERATED_EPISODE",
                     "causality_established":False,"observed_recovery_established":False,"production_authorized":False})
    return rows

def validate_graph(rows,graph):
    edges=set(graph.edges)
    for row in rows:
        resources=set(row["resources"])
        if not resources<=graph.nodes.keys() or not all(tuple(edge) in edges for edge in row["dependency_edges"]):
            raise ValueError("unverified episode topology")
        if any(s["resource"] not in resources for s in row["observations"]):
            raise ValueError("unbound episode observation")

def source_refs(step,snapshot):
    if snapshot is None: return {}
    raw,h,receipt=snapshot
    rows=json.loads(raw)
    if rows!=batches(step) or digest(rows)!=h:
        raise ValueError("invalid campaign snapshot")
    if receipt is None: return {}
    refs=json.loads(receipt)
    if len(refs)!=len(rows) or len({r["run_id"] for r in refs})!=len(rows):
        raise ValueError("invalid campaign receipt count")
    result={}
    for signals,r in zip(rows,refs):
        ident=signals[0]["enterprise"]["scenario"]["scenario_id"]
        if (r["scenario_id"]!=ident or r["resource"]!=signals[0]["resource"]
            or not re.fullmatch(r"RUN-[A-F0-9]{16}",r["run_id"]) or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",r["incident_id"])
            or len(r["evidence"])!=4 or len({e["evidence_id"] for e in r["evidence"]})!=4
            or any(not re.fullmatch(r"[a-f0-9]{64}",e["payload_hash"]) for e in r["evidence"])):
            raise ValueError("invalid campaign source")
        result[ident]={"scenario_id":ident,"resource":r["resource"],"run_id":r["run_id"],"incident_id":r["incident_id"],
                       "evidence_refs":r["evidence"],"relationship":"RELATED_MODELED_CASE_NOT_CAUSAL_PROOF"}
    return result

def store(db,step):
    rows=modeled(step)
    db.execute("INSERT INTO episodes(tick,payload,payload_hash) VALUES(?,?,?)",(step["tick"],json.dumps(rows,sort_keys=True),digest(rows)))

def read_recent(db,decode):
    records=[]
    missing=[]
    rows=db.execute("SELECT j.tick,j.step,j.step_hash,j.receipt,e.payload,e.payload_hash FROM journal j LEFT JOIN episodes e ON j.tick=e.tick ORDER BY j.tick DESC LIMIT 20").fetchall()
    for r in reversed(rows):
        step=decode(r[:4])
        if r[4] is None:
            missing.append(step["tick"])
            continue
        model=json.loads(r[4])
        if model!=modeled(step) or digest(model)!=r[5]:
            raise ValueError("corrupt episode journal")
        snapshot=db.execute("SELECT batches,batch_hash,receipt FROM scenarios WHERE tick=?",(step["tick"],)).fetchone()
        refs=source_refs(step,snapshot)
        for row in model:
            records.append({**row,"related_cases":[refs[i] for i in row["candidate_scenario_ids"] if i in refs],
                            "episode_sha256":digest(row)})
    return {"classification":"SYNTHETIC_MULTITICK_EPISODES_E12","version":VERSION,
            "current_tick":rows[0][0] if rows else 0,"records":records,"unavailable_pre_e12_ticks":missing,
            "production_authorized":False,"operational_decision":"DENY"}
