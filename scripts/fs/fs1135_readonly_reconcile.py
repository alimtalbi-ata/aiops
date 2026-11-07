#!/usr/bin/env python3
"""FS1135 read-only Core API / PostgreSQL KPI reconciliation.

Executed inside the existing Core container. No writes, no auth tokens printed.
"""
import collections
import json
import os
import sys
from datetime import datetime
import requests
from shared.db import db

CORE="http://127.0.0.1:810"
LIMIT=100
def emit(kind, **fields):
    print(json.dumps({"type":kind,**fields},ensure_ascii=False,default=str),flush=True)
def iso(x):
    return x.isoformat() if hasattr(x,"isoformat") else str(x)
def normalize(x):
    return json.loads(json.dumps(x,default=iso))
def get(path):
    r=requests.get(CORE+path,timeout=15)
    r.raise_for_status()
    return r.json()
def check(condition,code,**fields):
    if not condition:
        emit("mismatch",code=code,**fields)
        return False
    return True
def main():
    ok=True
    with db() as c:
        rows=c.execute("""select run_id,incident_id,mode,scenario_id,status,version,
                                 overall_confidence,created_at,started_at,completed_at
                          from aiops.runs order by created_at desc limit %s""",(LIMIT,)).fetchall()
        all_campaign=c.execute("""select count(*),count(*) filter (where status='RESOLVED'),
                          count(*) filter (where status='BLOCKED'),
                          count(*) filter (where status='FAILED')
                          from aiops.runs where scenario_id like 'FS1130-%'""").fetchone()
        telemetry=c.execute("""select
                          count(*) filter (where event_type='ANALYST_COMPLETED'),
                          count(*) filter (where event_type='CRITIC_COMPLETED'),
                          count(*) filter (where event_type in ('ANALYST_COMPLETED','CRITIC_COMPLETED')
                              and jsonb_typeof(payload->'llm_telemetry')='object'),
                          count(*) filter (where event_type in ('ANALYST_COMPLETED','CRITIC_COMPLETED')
                              and jsonb_typeof(payload->'llm_telemetry'->'total_tokens')='number')
                          from aiops.run_events""").fetchone()
    keys=("run_id","incident_id","mode","scenario_id","status","version","overall_confidence","created_at","started_at","completed_at")
    expected=[normalize(dict(zip(keys,row))) for row in rows]
    api=get("/api/runs")
    actual=api.get("items") if isinstance(api,dict) else None
    ok=check(isinstance(actual,list),"API_LIST_SHAPE") and ok
    if isinstance(actual,list):
        ok=check(len(actual)==len(expected),"API_LIST_COUNT",api=len(actual),db=len(expected)) and ok
        # Order of equal timestamps is undefined, so compare by run ID.
        api_by_id={str(x.get("run_id")):x for x in actual if isinstance(x,dict)}
        db_by_id={str(x["run_id"]):x for x in expected}
        ok=check(set(api_by_id)==set(db_by_id),"API_DB_RUN_IDS",api_count=len(api_by_id),db_count=len(db_by_id)) and ok
        for rid in set(api_by_id)&set(db_by_id):
            for key in ("status","mode","scenario_id"):
                if api_by_id[rid].get(key)!=db_by_id[rid].get(key):
                    ok=check(False,"RUN_FIELD_MISMATCH",run_id=rid,field=key) and ok
    # Select bounded recent run samples, including FS1130 when visible.
    selected=expected[:5]
    selected+=next(( [x] for x in expected if str(x.get("scenario_id") or "").startswith("FS1130-") and x not in selected),[])
    checked=0
    for run in selected:
        rid=str(run["run_id"])
        detail=get("/api/runs/"+rid)
        with db() as c:
            stage_count=c.execute("select count(*) from aiops.run_stage_state where run_id=%s",(rid,)).fetchone()[0]
            event_count=c.execute("select count(*) from aiops.run_events where run_id=%s",(rid,)).fetchone()[0]
            gate_count=c.execute("select count(*) from aiops.gates where run_id=%s",(rid,)).fetchone()[0]
            llm_events=c.execute("""select sequence,event_type,payload->'llm_telemetry'
                                   from aiops.run_events where run_id=%s
                                   and event_type in ('ANALYST_COMPLETED','CRITIC_COMPLETED')
                                   order by sequence""",(rid,)).fetchall()
        ok=check(detail.get("run",{}).get("status")==run["status"],"DETAIL_STATUS",run_id=rid) and ok
        for field,expected_count in (("stages",stage_count),("events",event_count),("gates",gate_count)):
            actual_count=len(detail.get(field,[]))
            ok=check(actual_count==expected_count,"DETAIL_COUNT",run_id=rid,field=field,api=actual_count,db=expected_count) and ok
        api_events={e["sequence"]:e for e in detail.get("events",[]) if isinstance(e,dict)}
        for sequence,event_type,usage in llm_events:
            ev=api_events.get(sequence,{})
            ok=check(ev.get("event_type")==event_type,"EVENT_TYPE",run_id=rid,sequence=sequence) and ok
            api_usage=(ev.get("payload") or {}).get("llm_telemetry")
            ok=check(normalize(api_usage)==normalize(usage),"EVENT_TELEMETRY",run_id=rid,sequence=sequence) and ok
        checked+=1
    emit("summary",result="PASS" if ok else "FAIL",mode="READ_ONLY_REAL_CORE_POSTGRES",
         api_recent_runs=len(actual) if isinstance(actual,list) else None,
         db_recent_runs=len(expected),detail_runs_checked=checked,
         fs1130_db_total=all_campaign[0],fs1130_resolved=all_campaign[1],
         fs1130_blocked=all_campaign[2],fs1130_failed=all_campaign[3],
         analyst_events=telemetry[0],critic_events=telemetry[1],
         llm_telemetry_events=telemetry[2],llm_events_with_numeric_total_tokens=telemetry[3],
         limitation="Historical FS1130 token usage cannot be reconstructed; API list limited to 100 latest runs",
         production_mutation="NONE")
    return 0 if ok else 2
if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        emit("fatal",error_type=type(exc).__name__,reason=str(exc)[:240])
        sys.exit(3)
