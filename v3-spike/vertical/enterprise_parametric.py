"""Opt-in seeded workload plan, independent of fixed acceptance fixtures.

Only logical ticks materialize modeled observations. No Core writes, external
measurements, confirmed impact, recovery or production action.
"""
import hashlib
import json
from enterprise_context import P, digest
from enterprise_scenarios import CATALOG, root_of

VERSION="E14_SEEDED_WORKLOAD_V1"
PAY=("USER-FIN-01","USER-FIN-02","USER-DIRECT-01")
CRM=("USER-SALES-01",)
HR=("USER-HR-01",)
PAR=PAY+CRM
ALL=PAR+HR
POOLS={"WAN":ALL,"IDENTITY":ALL,"STORAGE-PAR":PAR,"LINUX-PAR":PAR,
       "WIN-LYO":HR,"STORAGE-LYO":HR,"NET-LYO":HR,
       "APP-PAY":PAY,"APP-CRM":CRM,"APP-HR":HR}

def config(value):
    keys={"seed","horizon","frequency_pct","min_duration","max_duration","max_users"}
    if not isinstance(value,dict) or set(value)!=keys or any(type(value[k]) is not int for k in keys):
        raise ValueError("invalid campaign configuration")
    if not (0<=value["seed"]<=2147483647 and 8<=value["horizon"]<=120
            and 0<=value["frequency_pct"]<=100
            and 1<=value["min_duration"]<=value["max_duration"]<=8
            and 1<=value["max_users"]<=5):
        raise ValueError("configuration outside bounded laboratory limits")
    return dict(value)

def draw(seed,tick,label,modulus):
    return int.from_bytes(hashlib.sha256(f"{VERSION}:{seed}:{tick}:{label}".encode()).digest()[:8],"big")%modulus

def plan(value):
    cfg=config(value)
    seed=cfg["seed"]
    rows=[]
    for tick in range(1,cfg["horizon"]-cfg["min_duration"]+1):
        if draw(seed,tick,"start",100)>=cfg["frequency_pct"]: continue
        row=CATALOG[draw(seed,tick,"scenario",len(CATALOG))]
        ident,family,resource,app,group,user,metric,unit,nominal,abnormal,_,_=row
        duration=cfg["min_duration"]+draw(seed,tick,"duration",min(cfg["max_duration"],cfg["horizon"]-tick)-cfg["min_duration"]+1)
        pool=(user,) if user else POOLS[app or resource]
        selected=sorted(pool,key=lambda u:(draw(seed,tick,"user:"+u,2**32),u))
        count=1+draw(seed,tick,"population",min(len(selected),cfg["max_users"]))
        users=sorted(P+u for u in selected[:count])
        severity="critical" if draw(seed,tick,"severity",3)==0 else "warning"
        rows.append({"episode_id":f"E14-{seed}-{tick:03d}-{ident}","scenario_id":ident,"family":family,
                     "resource":root_of(row),"application_id":P+app if app else None,
                     "modeled_exposed_user_ids":users,"start_tick":tick,"duration_ticks":duration,
                     "recovery_tick":tick+duration,"severity":severity,"metric":metric,"unit":unit,
                     "baseline":nominal,"degraded":abnormal,"classification":"MODEL_GENERATED_PLAN"})
    return rows

def validate_graph(rows,graph):
    for row in rows:
        allowed=graph.scope(row["resource"])
        if not set(row["modeled_exposed_user_ids"])<=allowed["users"]:
            raise ValueError("invalid modeled population")
        if row["application_id"] and row["application_id"] not in allowed["applications"]:
            raise ValueError("invalid modeled application")
        if row["application_id"]:
            app=row["application_id"]
            users=graph.reverse({app},"uses")
            direct={u for u in users if graph.nodes[u]["type"]=="user"}
            groups={u for u in users if graph.nodes[u]["type"]=="user_group"}
            if not set(row["modeled_exposed_user_ids"])<=direct|graph.reverse(groups,"member_of"):
                raise ValueError("invalid modeled application population")

def read_profile(db):
    row=db.execute("SELECT payload,payload_hash FROM parametric_profile WHERE id=1").fetchone()
    if row is None: return None
    data=json.loads(row[0])
    if data!={"configuration":config(data["configuration"]),"plan":plan(data["configuration"]),"version":VERSION} or digest(data)!=row[1]:
        raise ValueError("corrupt campaign profile")
    return data

def configure(db,value):
    data={"configuration":config(value),"plan":plan(value),"version":VERSION}
    existing=read_profile(db)
    if existing is not None:
        if existing!=data: raise ValueError("immutable campaign profile")
        return existing
    if db.execute("SELECT 1 FROM journal LIMIT 1").fetchone():
        raise ValueError("configure before first tick in fresh dedicated world")
    db.execute("INSERT INTO parametric_profile(id,payload,payload_hash) VALUES(1,?,?)",(json.dumps(data,sort_keys=True),digest(data)))
    return data

def materialize(profile,step):
    tick=step["tick"]
    records=[]
    for row in profile["plan"]:
        if not row["start_tick"]<=tick<=row["recovery_tick"]: continue
        phase="ONSET" if tick==row["start_tick"] else "MODEL_RECOVERY" if tick==row["recovery_tick"] else "ACTIVE"
        records.append({**row,"tick":tick,"occurred_at":step["simulated_at"],"phase":phase,
                        "value":row["baseline"] if phase=="MODEL_RECOVERY" else row["degraded"],
                        "classification":"MODEL_GENERATED_OBSERVATION","observed_outage_established":False,
                        "observed_recovery_established":False,"production_authorized":False})
    return records

def store(db,step):
    profile=read_profile(db)
    if profile is None or step["tick"]>profile["configuration"]["horizon"]: return
    rows=materialize(profile,step)
    db.execute("INSERT INTO parametric_ticks(tick,payload,payload_hash) VALUES(?,?,?)",(step["tick"],json.dumps(rows,sort_keys=True),digest(rows)))

def timeline(db,decode):
    profile=read_profile(db)
    tick=db.execute("SELECT COALESCE(MAX(tick),0) FROM journal").fetchone()[0]
    output={"classification":"SYNTHETIC_PARAMETRIC_WORKLOAD_E14","state":"DISABLED" if profile is None else "CONFIGURED",
            "current_tick":tick,"configuration":None,"plan_sha256":None,"planned_episode_count":0,"records":[],
            "production_authorized":False,"operational_decision":"DENY"}
    if profile is None: return output
    horizon=profile["configuration"]["horizon"]
    output.update(configuration=profile["configuration"],plan_sha256=digest(profile),planned_episode_count=len(profile["plan"]))
    if tick>=horizon: output["state"]="HORIZON_COMPLETE"
    rows=db.execute("SELECT j.tick,j.step,j.step_hash,j.receipt,p.payload,p.payload_hash FROM journal j LEFT JOIN parametric_ticks p ON j.tick=p.tick WHERE j.tick<=? ORDER BY j.tick",(min(tick,horizon),)).fetchall()
    if len(rows)!=min(tick,horizon): raise ValueError("incomplete campaign journal")
    for r in rows:
        step=decode(r[:4])
        records=json.loads(r[4])
        if records!=materialize(profile,step) or digest(records)!=r[5]:
            raise ValueError("corrupt campaign observation")
        output["records"].extend(records)
    return output
