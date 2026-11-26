"""Disposable rootless CI proof of a real Temporal E17 action and independent Verify.

No product endpoint. The dedicated SDK worker owns the loopback target and
HITL gate in the same process, on a random task queue. The only activity is
a fixed reset, not a generic command. Real Core/Twin/Evidence/Policy are
read through the existing lab adapters. CI supplies the synthetic approval.
A lost activity result is a failed/unknown run, never an automatic retry.
"""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import runpy
import statistics
import sys
import threading
import time
import uuid

from temporalio import activity
from temporalio.api.enums.v1 import EventType
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker
from poc_temporal_e17_workflow import E17LabRecoveryWorkflow

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"vertical"))
from core_ingest import create_and_persist
from enterprise_clock import EnterpriseClock
from hitl_demo import DurableApprovalGate
from lab_context import dynamic_context
from recovery_verify import digest,verify_recovery

fixture=runpy.run_path(str(Path(__file__).with_name("poc-multiasset-observed.py")))
measure,now=fixture["measure"],fixture["now"]
resource,asset,application,*_=fixture["CONFIGS"][0]


def endpoint(value):
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{4,5}",value):
        raise ValueError("CI loopback endpoint required")
    port=int(value.rsplit(":",1)[1])
    if not 1024<=port<=65535 or port in (7770,7777,7790):
        raise ValueError("protected or invalid port")
    return port


async def history_receipt(client,rid):
    handle=client.get_workflow_handle(rid)
    result=await asyncio.wait_for(handle.result(),timeout=60)
    history=await asyncio.wait_for(handle.fetch_history(),timeout=10)
    scheduled=[e for e in history.events if e.event_type==EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED]
    completed=[e for e in history.events if e.event_type==EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED]
    assert len(scheduled)==len(completed)==1
    assert scheduled[0].activity_task_scheduled_event_attributes.activity_type.name=="v3_e17_reset_lab_http_delay"
    assert completed[0].activity_task_completed_event_attributes.scheduled_event_id==scheduled[0].event_id
    assert result["binding"]["workflow_id"]==rid
    assert result["status"]=="SIMULATED" and result["production_authorized"] is False
    return result,len(history.events)


async def execute(root,temporal,core,twin,evidence,policy):
    token=dict(line.split("=",1) for line in (root/"poc.env").read_text().splitlines())["V3_LAB_TOKEN"]
    isolated=root/"temporal-e17"
    isolated.mkdir(mode=0o700,exist_ok=False)
    gate=DurableApprovalGate(EnterpriseClock(isolated))
    def read_context(rid):
        return dynamic_context(core,token,rid,twin,evidence,resource,
                               include_signals=True,multiasset=True)
    identity=uuid.uuid4().hex
    base=dict(resource=resource,source="measured-recovery-ci",tenant="synthetic-demo",
              synthetic=True,severity="critical")
    scope=dict(asset_id=asset,application_id=application)
    def metric(phase,samples):
        return dict(base,id=identity+"-"+phase,kind="metric",
                    enterprise=dict(scope,occurred_at=now(),measurement={
                        "classification":"MEASURED_SYNTHETIC_LAB",
                        "method":"HTTP_MONOTONIC_MEDIAN_5","samples_ms":samples}),
                    observation=dict(metric="latency_ms",phase=phase,
                                     value=round(statistics.median(samples),3)))
    def event(name,message):
        return dict(base,id=identity+"-"+name,kind="event",
                    enterprise=dict(scope,occurred_at=now(),message=message))
    def publish(rows):
        result=create_and_persist(rows,core,token,evidence)
        assert result==create_and_persist(rows,core,token,evidence)
        return result["core"]["run"],result["stored_evidence"]
    client=await Client.connect(temporal)
    with fixture["LabRecoveryTarget"]() as target:
        thread=threading.Thread(target=target.serve_forever,daemon=True)
        thread.start()
        try:
            baseline=metric("baseline",measure(target))
            await asyncio.sleep(1.1)
            target.inject_fault()
            fault=event("fault","Controlled lab response delay applied")
            incident=metric("incident",measure(target))
            rows=[baseline,fault,incident]
            run,refs=publish(rows)
            rid,inc=run["run_id"],run["incident_id"]
            _,context=read_context(rid)
            assert context["diagnosis"]["hypothesis"]=="LATENCY_REGRESSION_OBSERVED"
            action_scope=target.bind(gate,inc,rid,refs,read_context=read_context,policy_port=policy)
            for approved in (False,True):
                key=gate.request(inc,rid,refs,lab_action=action_scope)["request_id"]
                decision=gate.decide(key,inc,rid,refs,approved,lab_action=action_scope)
                assert decision["decision"]==("SIMULATE_ONLY" if approved else "DENY")
                assert gate.decide(key,inc,rid,refs,True,lab_action=action_scope)["decision"]=="DENY"
                if not approved:
                    try:
                        target.simulate(decision["receipt_id"],decision["receipt_sha256"],workflow_id=rid)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("denied receipt accepted")
                    assert target.delay==fixture["CONFIGS"][0][-1]
            approval={k:decision[k] for k in ("receipt_id","receipt_sha256")}

            @activity.defn(name="v3_e17_reset_lab_http_delay")
            async def reset(args:dict)->dict:
                # The actual Temporal workflow identity, never an input field.
                info=activity.info()
                if info.workflow_id!=rid or info.attempt!=1 or args!=approval:
                    raise ValueError("foreign workflow, retry or approval")
                result=await asyncio.to_thread(target.simulate,args["receipt_id"],
                                              args["receipt_sha256"],workflow_id=info.workflow_id)
                if result["status"]!="SIMULATED":
                    raise RuntimeError("ambiguous lab action; manual review required")
                return result

            await asyncio.sleep(1.1)
            queue="aiops-v3-e17-lab-"+identity
            async with Worker(client,task_queue=queue,workflows=[E17LabRecoveryWorkflow],
                              activities=[reset],max_cached_workflows=0):
                handle=await client.start_workflow(E17LabRecoveryWorkflow.run,approval,
                    id=rid,task_queue=queue,execution_timeout=timedelta(seconds=75),
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
                receipt=await asyncio.wait_for(handle.result(),timeout=80)
            # Re-read persisted history after this dedicated worker stopped.
            persisted,events=await history_receipt(client,rid)
            assert persisted==receipt==target.read_action_result(receipt["receipt_id"])
            assert target.simulate(approval["receipt_id"],approval["receipt_sha256"],
                                   workflow_id=rid)["status"]=="UNKNOWN_BLOCKED"
            receipt_hash=digest(persisted)
            action=event("action","Temporal lab action receipt "+receipt_hash+"; original run "+rid)
            await asyncio.sleep(1.1)
            recovery=metric("recovery",measure(target))
            assert len(target.records)==15
            comparison,comparison_refs=publish(rows+[action,recovery])
            def read_receipt(receipt_id):
                if receipt_id!=persisted["receipt_id"]:
                    raise ValueError("unknown history receipt")
                return persisted
            result=verify_recovery(read_context=read_context,read_action_receipt=read_receipt,
                    original_run_id=rid,comparison_run_id=comparison["run_id"],
                    scope=[resource,asset,application],original_refs=refs,
                    comparison_refs=comparison_refs,action_receipt_id=persisted["receipt_id"],
                    action_receipt_sha256=receipt_hash)
            assert result["status"]=="RECOVERED"
            return {"classification":"V3_TEMPORAL_E17_LAB_RUNTIME","result":"PASS",
                    "workflow_id":rid,"history_events":events,"activities_completed":1,
                    "action_receipt":persisted,"action_receipt_sha256":receipt_hash,
                    "verification":result,"http_requests":15,
                    "core_business_stages_qualified":False,"production_authorized":False}
        finally:
            target.shutdown()
            thread.join(5)


async def readback(temporal,report):
    client=await Client.connect(temporal)
    receipt,events=await history_receipt(client,report["workflow_id"])
    assert receipt==report["action_receipt"] and digest(receipt)==report["action_receipt_sha256"]
    assert events==report["history_events"]
    return {"classification":"V3_TEMPORAL_E17_HISTORY_READBACK","result":"PASS",
            "workflow_id":report["workflow_id"],"action_receipt_sha256":digest(receipt),
            "history_events":events,"production_authorized":False}


if __name__=="__main__":
    if os.environ.get("GITHUB_ACTIONS")!="true" or os.getuid()==0:
        raise SystemExit("disposable rootless CI only")
    root=Path(sys.argv[1])
    if root!=Path("/tmp/aiops-v3-rootless-ci") or root.resolve()!=root or root.stat().st_uid!=os.getuid():
        raise SystemExit("dedicated CI root required")
    temporal=sys.argv[2]
    endpoint(temporal)
    if sys.argv[3:]==["readback"]:
        result=asyncio.run(readback(temporal,json.loads((root/"temporal-e17.json").read_text())))
    else:
        ports=[endpoint(v) for v in sys.argv[3:]]
        if len(ports)!=4 or len(set(ports+[endpoint(temporal)]))!=5:
            raise SystemExit("distinct service ports required")
        result=asyncio.run(execute(root,temporal,*ports))
    print(json.dumps(result,sort_keys=True))
