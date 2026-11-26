"""Runs inside the dedicated orchestration worker in disposable CI only."""
import asyncio
import json
import os
import re
import sys
import time
import requests
from temporalio.client import Client
from temporalio.api.enums.v1 import EventType

assert os.environ.get("AIOPS_V3_BOUNDARY")=="1"
assert os.environ["CORE_URL"]=="http://core:810"
assert os.environ["TEMPORAL_ADDRESS"]=="temporal:7233"
core="http://core:810"
worker="http://127.0.0.1:815"
headers={"Authorization":"Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"]}

def call(base,path,body=None):
    if body is None: r=requests.get(base+path,headers=headers,timeout=10)
    else: r=requests.post(base+path,json=body,headers=headers,timeout=10)
    r.raise_for_status()
    return r.json()

async def verify(rid):
    client=await Client.connect("temporal:7233")
    handle=client.get_workflow_handle(rid)
    result=await asyncio.wait_for(handle.result(),timeout=90)
    assert result=={"run_id":rid,"status":"BLOCKED","final_version":3,"reason":"V3_STAGE_ADAPTERS_NOT_QUALIFIED","executed_on_host":False,"production_authorized":False}
    history=await handle.fetch_history()
    assert sum(e.event_type==EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED for e in history.events)==2
    data=call(core,"/api/runs/"+rid)
    assert data["run"]["status"]=="BLOCKED" and data["run"]["version"]==3
    assert [e["status"] for e in data["events"]]==["CREATED","RUNNING","BLOCKED"]
    assert all(s["state"]=="PENDING" for s in data["stages"]) and not data["gates"]
    assert all(not e["evidence_ids"] for e in data["events"])
    assert call("http://evidence:812","/api/evidence?run_id="+rid)["items"]==[]
    return {"classification":"V3_TEMPORAL_BOUNDARY_RUNTIME","result":"PASS","run_id":rid,
            "workflow_id":rid,"history_events":len(history.events),"activities_completed":2,
            "core_status":"BLOCKED","business_stages_passed":0,"production_authorized":False}

if sys.argv[1:]==["unavailable"]:
    for _ in range(10):
        try:
            response=requests.get(worker+"/health",timeout=5)
            if response.status_code==503:
                print("V3 Temporal unavailable readiness PASS")
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    else: raise AssertionError("Worker remained ready without Temporal")
elif len(sys.argv)==3 and sys.argv[1]=="replay":
    rid=sys.argv[2]
    assert re.fullmatch(r"RUN-[A-F0-9]{16}",rid)
    print(json.dumps(asyncio.run(verify(rid)),sort_keys=True))
else:
    health=call(worker,"/health")
    assert health["classification"]=="V3_ORCHESTRATION_BOUNDARY" and not health["business_stages_qualified"]
    created=call(core,"/api/runs",{"mode":"DEMO","scenario_id":"CI-TEMPORAL-BOUNDARY","incident_id":"INC-CI-CONTEXT","idempotency_key":"ci-v3-temporal-boundary-v1"})
    rid=created["run_id"]
    assert re.fullmatch(r"RUN-[A-F0-9]{16}",rid) and created["status"]=="CREATED"
    args={"run_id":rid,"mode":"LIVE","scenario_id":"CI-TEMPORAL-BOUNDARY","version":1}
    denied=requests.post(worker+"/api/execution/start",headers=headers,json=args,timeout=10)
    assert denied.status_code==422
    assert call(core,"/api/runs/"+rid)["run"]["status"]=="CREATED"
    receipt=call(core,"/api/runs/"+rid+"/execute",{})
    assert receipt["workflow_id"]==rid
    print(json.dumps(asyncio.run(verify(rid)),sort_keys=True))
