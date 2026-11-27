"""Read the actual E17 Temporal history from inside the isolated Worker.
Publish only the allowlisted event sequence, identities and verified payloads.
This is a loss-limited history projection, not the raw protobuf history.
"""
import asyncio
import hashlib
import json
import os
import re
import sys
from temporalio.api.enums.v1 import EventType
from temporalio.client import Client

def require(ok, message):
    if not ok:
        raise ValueError(message)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

async def main(report):
    require(os.getenv("AIOPS_V3_BOUNDARY")=="1" and os.getenv("TEMPORAL_ADDRESS")=="temporal:7233",
            "isolated Worker required")
    rid=report["workflow_id"]
    receipt=report["action_receipt"]
    digest=hashlib.sha256(canonical(receipt)).hexdigest()
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid) and report["production_authorized"] is False
            and report["result"]=="PASS" and receipt["binding"]["workflow_id"]==rid
            and receipt["production_authorized"] is False and receipt["status"]=="SIMULATED"
            and digest==report["action_receipt_sha256"],"invalid report")
    approval={k:receipt["binding"][k] for k in ("receipt_id","receipt_sha256")}
    require(re.fullmatch(r"[a-f0-9]{64}",approval["receipt_sha256"])
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",approval["receipt_id"]),"invalid approval")
    client=await asyncio.wait_for(Client.connect("temporal:7233"),timeout=10)
    handle=client.get_workflow_handle(rid)
    history=await asyncio.wait_for(handle.fetch_history(),timeout=10)
    require(history.workflow_id==rid and len(history.events)==report["history_events"]
            and 5<=len(history.events)<=64,"history cardinality")
    allowed={"WORKFLOW_EXECUTION_STARTED","WORKFLOW_TASK_SCHEDULED","WORKFLOW_TASK_STARTED",
             "WORKFLOW_TASK_COMPLETED","ACTIVITY_TASK_SCHEDULED","ACTIVITY_TASK_STARTED",
             "ACTIVITY_TASK_COMPLETED","WORKFLOW_EXECUTION_COMPLETED"}
    rows=[]
    groups={}
    for event in history.events:
        kind=EventType.Name(event.event_type).removeprefix("EVENT_TYPE_")
        require(kind in allowed,"unexpected event kind")
        rows.append({"event_id":event.event_id,"event_type":kind,
                     "event_time":event.event_time.ToJsonString()})
        groups.setdefault(kind,[]).append(event)
    require([r["event_id"] for r in rows]==list(range(1,len(rows)+1)),"history sequence")
    def one(kind):
        require(len(groups.get(kind,[]))==1,"unexpected event count: "+kind)
        return groups[kind][0]
    start=one("WORKFLOW_EXECUTION_STARTED")
    scheduled=one("ACTIVITY_TASK_SCHEDULED")
    started=one("ACTIVITY_TASK_STARTED")
    completed=one("ACTIVITY_TASK_COMPLETED")
    terminal=one("WORKFLOW_EXECUTION_COMPLETED")
    a=start.workflow_execution_started_event_attributes
    b=scheduled.activity_task_scheduled_event_attributes
    c=started.activity_task_started_event_attributes
    d=completed.activity_task_completed_event_attributes
    e=terminal.workflow_execution_completed_event_attributes
    require(start.event_id==1 and terminal.event_id==len(rows)
            and start.event_id<scheduled.event_id<started.event_id<completed.event_id<terminal.event_id
            and a.workflow_type.name=="E17ProductRecoveryWorkflow"
            and a.task_queue.name==b.task_queue.name=="aiops-v3-boundary"
            and b.activity_type.name=="v3_e17_reset_lab_http_delay" and b.retry_policy.maximum_attempts==1
            and c.attempt==1 and re.fullmatch(r"aiops-v3-[a-f0-9]{32}",c.identity)
            and c.scheduled_event_id==d.scheduled_event_id==scheduled.event_id
            and d.started_event_id==started.event_id,"unverified activity links")
    for payload,expected in ((a.input.payloads,approval),(b.input.payloads,approval),
                             (d.result.payloads,receipt),(e.result.payloads,receipt)):
        decoded=await client.data_converter.decode(payload)
        require(canonical(decoded)==canonical([expected]),"history payload mismatch")
    # Only already verified synthetic payloads are exported, not arbitrary event metadata.
    return {"classification":"V3_E17_TEMPORAL_HISTORY_PROJECTION",
            "workflow_id":rid,"action_receipt_sha256":digest,"events":rows,
            "workflow_type":a.workflow_type.name,"activity_type":b.activity_type.name,
            "activity_identity":c.identity,"activity_attempt":c.attempt,
            "scheduled_event_id":scheduled.event_id,"started_event_id":started.event_id,
            "completed_event_id":completed.event_id,"approval":approval,
            "activity_result":receipt,"workflow_result":receipt,
            "production_authorized":False,"raw_history_exported":False}

if __name__=="__main__":
    print(json.dumps(asyncio.run(main(json.load(sys.stdin))),sort_keys=True))
