"""Read-only authenticated receipt projection for the dedicated E17 lab workflow.

Temporal history is the source of truth inside this lab trust boundary.
A receipt is not a capability, proof of causality, or production permission.
The original Core run remains independent of the lab workflow lifecycle.
"""
import asyncio
import hashlib
import json
import re
from datetime import datetime
from temporalio.api.enums.v1 import EventType


def require(condition):
    if not condition:
        raise ValueError("unverified E17 receipt")


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def matches(value,pattern):
    return isinstance(value,str) and re.fullmatch(pattern,value) is not None


def validate_receipt(receipt,run):
    require(isinstance(receipt,dict) and set(receipt)=={
        "classification","status","receipt_id","binding","completed_at",
        "operational_decision","executed_on_host","production_authorized"})
    require(receipt["classification"]=="SYNTHETIC_LAB_ACTION_RECEIPT"
            and receipt["status"]=="SIMULATED" and receipt["operational_decision"]=="DENY"
            and receipt["executed_on_host"] is False and receipt["production_authorized"] is False
            and matches(receipt["receipt_id"],r"ACT-[a-f0-9]{32}"))
    stamp=receipt["completed_at"]
    require(isinstance(stamp,str) and datetime.strptime(stamp,"%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")==stamp)
    binding=receipt["binding"]
    require(isinstance(binding,dict) and set(binding)=={
        "run_id","workflow_id","incident_id","context_sha256","receipt_id","receipt_sha256","lab_action"})
    require(binding["run_id"]==binding["workflow_id"]==run["run_id"]
            and binding["incident_id"]==run["incident_id"]
            and matches(binding["context_sha256"],r"[a-f0-9]{64}")
            and matches(binding["receipt_id"],r"HITL-[a-f0-9]{32}")
            and matches(binding["receipt_sha256"],r"[a-f0-9]{64}"))
    scope=binding["lab_action"]
    require(isinstance(scope,dict) and set(scope)=={"action","resource","target_id"}
            and scope["action"]=="RESET_LAB_HTTP_DELAY" and scope["resource"]=="NODE-CI-ROOT"
            and matches(scope["target_id"],r"[a-f0-9]{32}"))


async def project_receipt(client,run):
    rid=run["run_id"]
    require(matches(rid,r"RUN-[A-F0-9]{16}") and run["mode"]=="DEMO"
            and run["scenario_id"]=="CI-INGEST"
            and matches(run["incident_id"],r"INC-CI-INGEST-[a-f0-9]{32}"))
    handle=client.get_workflow_handle(rid)
    history=await asyncio.wait_for(handle.fetch_history(),timeout=8)
    events=history.events
    require(history.workflow_id==rid and 1<=len(events)<=64)
    def one(kind):
        found=[event for event in events if event.event_type==kind]
        require(len(found)==1)
        return found[0]
    start=one(EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED)
    scheduled=one(EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED)
    active=one(EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED)
    completed=one(EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED)
    final=one(EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED)
    require(events[0]==start and events[-1]==final
            and start.event_id<scheduled.event_id<active.event_id<completed.event_id<final.event_id)
    workflow=start.workflow_execution_started_event_attributes
    activity=scheduled.activity_task_scheduled_event_attributes
    attempt=active.activity_task_started_event_attributes
    result=completed.activity_task_completed_event_attributes
    require(((workflow.workflow_type.name=="E17LabRecoveryWorkflow"
              and matches(workflow.task_queue.name,r"aiops-v3-e17-lab-[a-f0-9]{32}"))
             or (workflow.workflow_type.name=="E17ProductRecoveryWorkflow"
                 and workflow.task_queue.name=="aiops-v3-boundary"))
            and activity.task_queue.name==workflow.task_queue.name
            and activity.activity_type.name=="v3_e17_reset_lab_http_delay"
            and activity.retry_policy.maximum_attempts==1 and attempt.attempt==1
            and attempt.scheduled_event_id==scheduled.event_id
            and result.scheduled_event_id==scheduled.event_id
            and result.started_event_id==active.event_id)
    activity_values=await client.data_converter.decode(result.result.payloads)
    workflow_values=await client.data_converter.decode(final.workflow_execution_completed_event_attributes.result.payloads)
    require(len(activity_values)==1 and activity_values==workflow_values)
    receipt=activity_values[0]
    validate_receipt(receipt,run)
    approval=await client.data_converter.decode(activity.input.payloads)
    submitted=await client.data_converter.decode(workflow.input.payloads)
    binding=receipt["binding"]
    require(approval==submitted==[{"receipt_id":binding["receipt_id"],"receipt_sha256":binding["receipt_sha256"]}])
    return {"classification":"V3_E17_WORKER_RECEIPT_READBACK","run_id":rid,
            "action_receipt":receipt,"action_receipt_sha256":digest(receipt),
            "history_events":len(events),"activities_completed":1,
            "operational_decision":"DENY","production_authorized":False,
            "core_business_stages_qualified":False}
