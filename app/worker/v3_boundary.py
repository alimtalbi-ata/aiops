"""Opt-in V3 POC worker using Temporal SDK and existing Core command receipts.

Never starts the historical generic business-stage workflow.
"""
import asyncio
import hmac
import logging
from datetime import timedelta
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from temporalio import activity
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker
from shared.http import get_json, post_json
from worker.v3_boundary_workflow import V3BoundaryWorkflow

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

async def worker_loop():
    global client
    while True:
        try:
            connected=await Client.connect(TEMP)
            async with Worker(connected,task_queue=QUEUE,workflows=[V3BoundaryWorkflow],activities=[start_run,block_run]):
                client=connected
                logger.info('V3 boundary worker registered queue=%s',QUEUE)
                await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('V3 boundary worker loop failed: %s',type(exc).__name__)
        finally:
            client=None
        await asyncio.sleep(2)

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
    if c is None:
        raise HTTPException(503,"Temporal worker not connected")
    async def pollers(kind):
        response=await c.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
            namespace=c.namespace,task_queue=TaskQueue(name=QUEUE),task_queue_type=kind))
        return any(p.identity==c.identity for p in response.pollers)
    try:
        healthy,workflow_poller,activity_poller=await asyncio.wait_for(asyncio.gather(
            c.service_client.check_health(),
            pollers(TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW),
            pollers(TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY)),timeout=3)
    except Exception:
        raise HTTPException(503,"Temporal service unavailable")
    if not (healthy and workflow_poller and activity_poller) or c is not client:
        raise HTTPException(503,"Temporal worker not ready")
    return c

@app.get("/health")
async def health():
    await ready()
    return {"status":"ok","component":"worker","executor":"temporal","task_queue":QUEUE,
            "workflow_poller":True,"activity_poller":True,"classification":"V3_ORCHESTRATION_BOUNDARY","business_stages_qualified":False,"production_authorized":False}

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
