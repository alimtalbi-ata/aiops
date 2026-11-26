"""Opt-in, fixed synthetic E17 activity. No caller-supplied host or command."""
import asyncio
import http.client
import json
import os
from temporalio import activity
from worker.v3_e17_receipt import matches,require,validate_receipt

def enabled():
    return (os.environ.get("AIOPS_V3_E17_TARGET")=="http://e17-target:816"
            and matches(os.environ.get("V3_E17_ACTIVITY_TOKEN"),r"[a-f0-9]{64}")
            and os.environ.get("V3_E17_ACTIVITY_TOKEN")!=os.environ.get("AIOPS_INTERNAL_TOKEN"))

def validate_approval(args):
    require(isinstance(args,dict) and set(args)=={"receipt_id","receipt_sha256"}
            and matches(args["receipt_id"],r"HITL-[a-f0-9]{32}")
            and matches(args["receipt_sha256"],r"[a-f0-9]{64}"))

def read_json(host,port,method,path,token,body=None,timeout=8):
    connection=http.client.HTTPConnection(host,port,timeout=timeout)
    try:
        connection.request(method,path,body=None if body is None else json.dumps(body),
                           headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
        response=connection.getresponse()
        raw=response.read(65537)
        require(response.status==200 and len(raw)<=65536)
        return json.loads(raw)
    finally:
        connection.close()

def canonical_run(rid):
    require(enabled() and matches(rid,r"RUN-[A-F0-9]{16}")
            and os.environ.get("AIOPS_V3_BOUNDARY")=="1"
            and os.environ.get("CORE_URL")=="http://core:810"
            and os.environ.get("TEMPORAL_ADDRESS")=="temporal:7233")
    token=os.environ["AIOPS_INTERNAL_TOKEN"]
    require(32<=len(token)<=256 and all(33<=ord(c)<=126 for c in token))
    run=read_json("core",810,"GET","/api/runs/"+rid,token)["run"]
    require(run["run_id"]==rid and run["mode"]=="DEMO" and run["scenario_id"]=="CI-INGEST"
            and run["status"]=="CREATED" and matches(run["incident_id"],r"INC-CI-INGEST-[a-f0-9]{32}"))
    return run

def reset(rid,args):
    validate_approval(args)
    run=canonical_run(rid)
    receipt=read_json("e17-target",816,"POST","/internal/e17/reset",
                      os.environ["V3_E17_ACTIVITY_TOKEN"],{"workflow_id":rid,**args},timeout=20)
    validate_receipt(receipt,run)
    binding=receipt["binding"]
    require(binding["receipt_id"]==args["receipt_id"] and binding["receipt_sha256"]==args["receipt_sha256"])
    require(canonical_run(rid)==run)
    return receipt

@activity.defn(name="v3_e17_reset_lab_http_delay")
async def reset_lab_http_delay(args:dict)->dict:
    info=activity.info()
    require(info.attempt==1 and info.workflow_type=="E17ProductRecoveryWorkflow"
            and info.task_queue=="aiops-v3-boundary")
    return await asyncio.to_thread(reset,info.workflow_id,args)
