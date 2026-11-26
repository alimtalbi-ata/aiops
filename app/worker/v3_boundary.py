"""Opt-in V3 POC worker using Temporal SDK and existing Core command receipts.

Never starts the historical generic business-stage workflow.
"""
import asyncio
import hmac
import logging
import uuid
from datetime import timedelta
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from temporalio import activity
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.api.enums.v1 import TaskQueueType, TaskQueueKind
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker
from shared.http import get_json, post_json
from worker.v3_boundary_workflow import V3BoundaryWorkflow, V3ReadinessWorkflow

if os.getenv("AIOPS_V3_BOUNDARY")!="1":
    raise RuntimeError("Explicit V3 boundary profile required")
CORE=os.environ["CORE_URL"]
TEMP=os.environ["TEMPORAL_ADDRESS"]
TOKEN=os.environ["AIOPS_INTERNAL_TOKEN"]
if CORE!="http://core:810" or TEMP!="temporal:7233" or len(TOKEN)<32:
    raise RuntimeError("Dedicated V3 service endpoints required")
QUEUE="aiops-v3-boundary"
SCENARIO="CI-TEMPORAL-BOUNDARY"
client=None
probe_verified=False
logger=logging.getLogger('uvicorn.error')

def validate(args):
    if (not isinstance(args,dict) or set(args)!={"run_id","mode","scenario_id","version"}
        or not isinstance(args["run_id"],str) or not re.fullmatch(r"RUN-[A-F0-9]{16}",args["run_id"])
        or args["mode"]!="DEMO" or args["scenario_id"]!=SCENARIO
        or type(args["version"]) is not int or args["version"]<1):
        raise ValueError("Only dedicated synthetic DEMO boundary runs accepted")

def read_run(args):
    validate(args)
    run=get_json(CORE,"/api/runs/"+args["run_id"],timeout=3,token=TOKEN)["run"]
    if (run["run_id"]!=args["run_id"] or run["mode"]!="DEMO" or run["scenario_id"]!=SCENARIO
        or run["incident_id"]!="INC-CI-CONTEXT"):
        raise ValueError("Core binding mismatch")
    return run

def command(args,action,states):
    run=read_run(args)
    if run["status"] not in states:
        raise ValueError("Invalid boundary run state")
    rid=args["run_id"]
    result=post_json(CORE,"/api/runs/"+rid+"/command",
        {"expected_version":args["version"],"idempotency_key":"V3-BOUNDARY-"+action+"-"+rid,"command":action},timeout=5,token=TOKEN)
    expected={"START":"RUNNING","BLOCK":"BLOCKED"}[action]
    if result["run_id"]!=rid or result["status"]!=expected or result["version"]!=args["version"]+1:
        raise ValueError("Unverified Core command receipt")
    return result

@activity.defn(name="v3_boundary_start")
async def start_run(args):
    return await asyncio.to_thread(command,args,"START",("CREATED","RUNNING"))

@activity.defn(name="v3_boundary_block")
async def block_run(args):
    return await asyncio.to_thread(command,args,"BLOCK",("RUNNING","BLOCKED"))

@activity.defn(name="v3_boundary_probe")
async def readiness_activity(nonce:str):
    if not re.fullmatch(r"[a-f0-9]{32}",nonce):
        raise ValueError("invalid probe")
    return nonce

async def poller_diagnostics(c):
    for kind in (TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY):
        try:
            response=await asyncio.wait_for(c.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
                namespace=c.namespace,task_queue=TaskQueue(name=QUEUE,kind=TaskQueueKind.TASK_QUEUE_KIND_NORMAL),
                task_queue_type=kind)),timeout=3)
            logger.info("V3 task queue type=%s pollers=%s own_identity=%s",kind,len(response.pollers),any(p.identity==c.identity for p in response.pollers))
        except Exception as exc:
            logger.warning("V3 task queue diagnostic type=%s error=%s",kind,type(exc).__name__)

async def report_probe_failure(handle,c):
    if handle is not None:
        try:
            history=await asyncio.wait_for(handle.fetch_history(),timeout=8)
            logger.error("V3 readiness failure events=%s",[e.event_type for e in history.events[-30:]])
            for e in history.events[-30:]:
                for field in ("workflow_task_failed_event_attributes","activity_task_failed_event_attributes","workflow_execution_failed_event_attributes"):
                    if e.HasField(field):
                        attr=getattr(e,field)
                        if attr.HasField("failure"):
                            logger.error("V3 readiness failure: %s",attr.failure.message.replace(TOKEN,"[redacted]")[:300])
        except Exception as exc:
            logger.error("V3 readiness history unavailable: %s",type(exc).__name__)
    await poller_diagnostics(c)

async def worker_loop():
    global client,probe_verified
    identity="aiops-v3-"+uuid.uuid4().hex
    for attempt in range(3):
        handle=None
        worker_task=None
        engine=None
        phase="connect"
        try:
            connected=await asyncio.wait_for(Client.connect(TEMP,identity=identity),timeout=10)
            phase="register"
            engine=Worker(connected,task_queue=QUEUE,identity=identity,
                          workflows=[V3BoundaryWorkflow,V3ReadinessWorkflow],
                          activities=[start_run,block_run,readiness_activity],
                          max_cached_workflows=0,graceful_shutdown_timeout=timedelta(seconds=5))
            worker_task=asyncio.create_task(engine.run())
            client=connected
            logger.info("V3 boundary worker started queue=%s attempt=%s",QUEUE,attempt+1)
            phase="submit"
            nonce=uuid.uuid4().hex
            logger.info("V3 readiness submitting probe id=V3-READINESS-%s",nonce)
            handle=await asyncio.wait_for(connected.start_workflow(V3ReadinessWorkflow.run,nonce,
                id="V3-READINESS-"+nonce,task_queue=QUEUE,execution_timeout=timedelta(seconds=30),
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE),timeout=12)
            logger.info("V3 readiness submitted probe id=%s",handle.id)
            phase="result"
            actual=await asyncio.wait_for(handle.result(),timeout=35)
            if actual!=nonce or worker_task.done():
                raise ValueError("readiness result mismatch or worker exited")
            probe_verified=True
            logger.info("V3 readiness workflow and activity PASS")
            await poller_diagnostics(connected)
            phase="polling"
            await worker_task
            raise RuntimeError("worker exited")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("V3 boundary worker attempt failed phase=%s error=%s",phase,type(exc).__name__)
            if client is not None:
                await report_probe_failure(handle,client)
        finally:
            client=None
            probe_verified=False
            if engine is not None:
                try:
                    await asyncio.wait_for(engine.shutdown(),timeout=10)
                except Exception as exc:
                    logger.error("V3 worker shutdown incomplete: %s",type(exc).__name__)
            if worker_task is not None:
                if not worker_task.done():
                    worker_task.cancel()
                else:
                    try: worker_task.result()
                    except asyncio.CancelledError: pass
                    except Exception as exc:
                        logger.error("V3 worker task failed: %s",type(exc).__name__)
        await asyncio.sleep(2)
    logger.error("V3 readiness attempts exhausted; restart required")

@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(worker_loop())
    try:
        yield
    finally:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

app=FastAPI(title="AIOps V3 isolated orchestration boundary",lifespan=lifespan)

async def ready():
    c=client
    if c is None or not probe_verified:
        raise HTTPException(503,"Temporal functional readiness not verified")
    try:
        healthy=await asyncio.wait_for(c.service_client.check_health(),timeout=3)
    except Exception:
        raise HTTPException(503,"Temporal service unavailable")
    if not healthy or c is not client or not probe_verified:
        raise HTTPException(503,"Temporal worker not ready")
    return c

@app.get("/health")
async def health():
    await ready()
    return {"status":"ok","component":"worker","executor":"temporal","task_queue":QUEUE,
            "readiness_workflow_verified":True,"readiness_activity_verified":True,"classification":"V3_ORCHESTRATION_BOUNDARY","business_stages_qualified":False,"production_authorized":False}

@app.post("/api/execution/start")
async def start(args:dict,authorization:str|None=Header(default=None)):
    if not hmac.compare_digest(authorization or "","Bearer "+TOKEN):
        raise HTTPException(401,"Invalid internal token")
    try: validate(args)
    except ValueError: raise HTTPException(422,"Unsupported boundary request")
    c=await ready()
    try: run=await asyncio.to_thread(read_run,args)
    except Exception: raise HTTPException(422,"Unverified Core run")
    if run["status"]!="CREATED" or run["version"]!=args["version"]:
        raise HTTPException(409,"Run not executable")
    try:
        h=await c.start_workflow(V3BoundaryWorkflow.run,args,id=args["run_id"],task_queue=QUEUE,
                                 id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,execution_timeout=timedelta(seconds=75))
        return {"workflow_id":h.id,"run_id":args["run_id"],"executor":"temporal","production_authorized":False}
    except WorkflowAlreadyStartedError:
        return {"workflow_id":args["run_id"],"run_id":args["run_id"],"executor":"temporal","idempotent":True,"production_authorized":False}


@app.get("/api/v3/lab/e17/receipt/{run_id}")
async def e17_receipt(run_id:str,authorization:str|None=Header(default=None)):
    """Internal synthetic read only; never submit or repeat an action."""
    if not hmac.compare_digest(authorization or "","Bearer "+TOKEN):
        raise HTTPException(401,"Invalid internal token")
    if not re.fullmatch(r"RUN-[A-F0-9]{16}",run_id):
        raise HTTPException(422,"Unsupported run identity")
    c=await ready()
    try:
        run=(await asyncio.to_thread(get_json,CORE,"/api/runs/"+run_id,timeout=3,token=TOKEN))["run"]
        if run.get("run_id")!=run_id:
            raise ValueError("foreign Core run")
        from worker.v3_e17_receipt import project_receipt
        result=await asyncio.wait_for(project_receipt(c,run),timeout=10)
        if c is not client or not probe_verified:
            raise HTTPException(503,"Worker changed during receipt read")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("E17 receipt unavailable: %s",type(exc).__name__)
        raise HTTPException(404,"Verified E17 receipt unavailable")
