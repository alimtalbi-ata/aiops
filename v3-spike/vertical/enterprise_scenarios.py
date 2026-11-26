"""Versioned deterministic multi-domain incident campaign (all signals model-generated)."""
from datetime import datetime,timedelta
import math

P="NODE-CI-ENT-"
ROOT="NODE-CI-ROOT"
# id, family, root, app, group, user, metric, unit, normal, abnormal, log, event
CATALOG=(
 ("WAN_LOSS","network","WAN",None,None,None,"packet_loss","percent",0,35,"Synthetic intersite packet loss","Modeled WAN link instability"),
 ("DISK_FULL","storage","STORAGE-PAR",None,None,None,"capacity_used","percent",63,98,"Synthetic storage capacity warning","Modeled disk capacity threshold exceeded"),
 ("AUTH_FAILURE","identity","IDENTITY",None,None,None,"auth_failure_rate","percent",1,72,"Synthetic directory login failures across applications","Modeled shared identity service degradation"),
 ("DB_LOCK","database","DB-PAY","APP-PAY",None,None,"lock_wait_ms","ms",5,2500,"Synthetic transaction lock waits","Modeled database lock contention"),
 ("CPU_SATURATION","compute","LINUX-PAR",None,None,None,"cpu_utilization","percent",25,97,"Synthetic Linux worker saturation","Modeled compute resource pressure"),
 ("HR_HTTP_ERRORS","application","ASSET-LYO","APP-HR","GROUP-HR","USER-HR-01","http_error_rate","percent",0.5,45,"Synthetic HR request failures","Modeled HR application error threshold"),
 ("FIN_DEVICE_FAILURE","endpoint","PC-FIN-01","APP-PAY",None,"USER-FIN-01","device_error_count","count",0,12,"Synthetic Finance workstation errors","Modeled individual device fault"),
 ("CRM_TIMEOUT","application","ROOT","APP-CRM","GROUP-SALES","USER-SALES-01","request_timeout_rate","percent",0.2,48,"Synthetic CRM customer search timeout","Modeled CRM application timeout"),
 ("MEMORY_PRESSURE","compute","WIN-LYO",None,None,None,"memory_utilization","percent",48,96,"Synthetic Windows runtime memory pressure","Modeled memory capacity threshold"),
 ("IO_STALL","storage","STORAGE-LYO",None,None,None,"io_wait_ms","ms",4,850,"Synthetic storage I/O delay","Modeled Lyon storage stall"),
 ("DB_POOL_EXHAUSTION","database","DB-CRM","APP-CRM",None,None,"connection_pool_used","percent",30,100,"Synthetic CRM connection pool exhausted","Modeled connection exhaustion"),
 ("LOCAL_NETWORK_LOSS","network","NET-LYO",None,None,None,"packet_loss","percent",0,65,"Synthetic Lyon access connectivity errors","Modeled local network interruption"),
 ("SALES_DEVICE_FAILURE","endpoint","PC-SALES-01","APP-CRM",None,"USER-SALES-01","device_error_count","count",0,9,"Synthetic sales workstation failure","Modeled individual access disruption"),
 ("PAY_DIRECT_ERROR","application","ROOT","APP-PAY",None,"USER-DIRECT-01","http_error_rate","percent",0.2,29,"Synthetic direct Payments user reports failed requests","Modeled individual report, not population outage"),
 ("DB_REPLICA_LAG","database","DB-HR","APP-HR",None,None,"replication_lag_s","seconds",1,180,"Synthetic HR replica delay","Modeled database replication lag"),
 ("HR_DEVICE_FAILURE","endpoint","PC-HR-01","APP-HR",None,"USER-HR-01","device_error_count","count",0,15,"Synthetic HR device connection failure","Modeled individual HR endpoint fault"),
)
BY_ID={r[0]:r for r in CATALOG}
VERSION="E10_CAMPAIGN_V1"

def root_of(row):
    return ROOT if row[2]=="ROOT" else P+row[2]

def describe():
    return [{"scenario_id":r[0],"family":r[1],"resource":root_of(r),"metric":r[6],"unit":r[7],
             "baseline":r[8],"incident":r[9],"classification":"MODEL_GENERATED"} for r in CATALOG]

def validate_metadata(meta,kind,scope):
    if not isinstance(meta,dict) or set(meta)!={"classification","campaign","scenario_id","tick","metric","unit","phase","value"}:
        raise ValueError("invalid scenario metadata")
    ident=meta["scenario_id"]
    if not isinstance(ident,str) or ident not in BY_ID:
        raise ValueError("unknown scenario")
    row=BY_ID[ident]
    tick=meta["tick"]
    if (meta["classification"]!="MODEL_GENERATED" or meta["campaign"]!=VERSION
        or type(tick) is not int or not 1<=tick<=10000 or ident not in {r[0] for r in selected(tick)}
        or meta["metric"]!=row[6] or meta["unit"]!=row[7]):
        raise ValueError("invalid scenario identity")
    if kind=="metric":
        phase=meta["phase"]
        if phase not in ("baseline","incident") or type(meta["value"]) not in (int,float) or not math.isfinite(meta["value"]) or meta["value"]!=row[8 if phase=="baseline" else 9]:
            raise ValueError("invalid modeled metric")
    elif meta["phase"]!=kind or meta["value"] is not None:
        raise ValueError("invalid modeled event")
    expected_asset=P+("ASSET-PAR" if row[2]=="ROOT" else row[2])
    if scope["asset_id"]!=expected_asset:
        raise ValueError("scenario asset mismatch")
    for field,value in zip(("application_id","group_id","user_id"),row[3:6]):
        if scope.get(field)!=(P+value if value else None):
            raise ValueError("scenario subject mismatch")
    return row

def selected(tick):
    index=((tick-1)*2)%len(CATALOG)
    return CATALOG[index:index+2]

def batches(step):
    tick=step["tick"]
    at=datetime.strptime(step["simulated_at"],"%Y-%m-%dT%H:%M:%SZ")
    output=[]
    for row in selected(tick):
        ident,family,resource,app,group,user,metric,unit,normal,abnormal,log,event=row
        scope={"asset_id":P+("ASSET-PAR" if resource=="ROOT" else resource)}
        for field,value in zip(("application_id","group_id","user_id"),(app,group,user)):
            if value: scope[field]=P+value
        base={"source":"enterprise-scenario-e10","tenant":"synthetic-demo","synthetic":True,
              "resource":root_of(row),"severity":"critical" if family!="endpoint" else "warning"}
        signals=[]
        for kind,phase,value,offset,message in (("metric","baseline",normal,-30,None),("metric","incident",abnormal,0,None),("log","log",None,1,log),("event","event",None,2,event)):
            meta={"classification":"MODEL_GENERATED","campaign":VERSION,"scenario_id":ident,"tick":tick,"metric":metric,"unit":unit,"phase":phase,"value":value}
            context=dict(scope,occurred_at=(at+timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ"),scenario=meta)
            if message: context["message"]=message
            signals.append(dict(base,id=f"e10-{tick}-{ident.lower()}-{phase}",kind=kind,enterprise=context))
        output.append(signals)
    return output
