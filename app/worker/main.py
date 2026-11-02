import os,asyncio
import requests
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from shared.http import post_json
from shared.simulation_policy_contract import policy_command_for_mode
from worker.hitl_reject_terminal_runtime import recover_terminal_once, validate_request, UnqualifiedTerminal
from worker.temporal_workflows import IncidentWorkflow, TerminalRejectWorkflow, AcmeSimulatedHitlWorkflow
from worker.acme_simulated_hitl import (SandboxDenied, capability, validate_intent, simulate_no_effect)
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
TEMP=os.getenv('TEMPORAL_ADDRESS','aiops2-temporal:7233')
def call(method,url,payload): return post_json(url.split('/api/')[0],'/api/'+url.split('/api/',1)[1],payload,timeout=15,token=ADMIN)
@activity.defn
async def start_run(a): return call('POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'START-'+a['run_id'],'command':'START'})
@activity.defn
async def execute_stage(a):
    rid,version,stage,mode,scenario=a['run_id'],a['version'],a['stage'],a['mode'],a['scenario_id']
    # Reject unknown modes before Core events, Twin changes or Evidence writes.
    policy_command = policy_command_for_mode(mode)
    started=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':version,'stage':stage,'event_type':'STAGE_STARTED','event_key':f'{stage}:START','status':'RUNNING','confidence':None,'payload':{'attempt':activity.info().attempt,'executor':'temporal'}})
    v=started['version']
    try:
        # This baseline has no qualified LIVE evidence/CMDB/RAG/analyst/critic/remediation adapters.
        # Never manufacture evidence or confidence values for a LIVE run.
        if mode == 'LIVE':
            blocked = call('POST',f'{CORE}/api/runs/{rid}/events',{
                'expected_version':v,
                'stage':stage,
                'event_type':'LIVE_ADAPTER_UNAVAILABLE',
                'event_key':f'{stage}:LIVE-ADAPTER-UNAVAILABLE',
                'status':'BLOCKED',
                'decision':'HUMAN_APPROVAL',
                'confidence':0.0,
                'payload':{
                    'reason':'LIVE execution is disabled until real evidence adapters and policy/HITL qualification are implemented',
                    'synthetic_evidence_created':False,
                    'stage_adapter_qualified':False,
                },
            })
            state = call('POST',f'{CORE}/api/runs/{rid}/command',{
                'expected_version':blocked['version'],
                'idempotency_key':f'LIVE-BLOCK-{rid}',
                'command':'BLOCK',
            })
            return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':state['version'],'sequence':blocked['sequence']}
        synthetic=True
        if synthetic and stage=='OBSERVE':
            post_json(TWIN,'/api/twin/synthetic-event',{'action':'SET_STATE','target_node_id':'ACME-SAN-FABRIC-A','run_id':rid,'payload':{'state':'DEGRADED','health':0.42}},token=ADMIN)
            post_json(TWIN,'/api/twin/synthetic-event',{'action':'OBSERVE','target_node_id':'ACME-SAN-FABRIC-A','run_id':rid,'payload':{'metric':'fc_errors','value':184,'unit':'errors/min','status':'CRITICAL'}},token=ADMIN)
        ev=post_json(EVID,'/api/evidence',{'source':f'run:{rid}:{stage.lower()}','claim':f'{stage} completed for scenario {scenario}','confidence':0.94 if stage not in ('DGX_ANALYST','DGX_CRITIC') else 0.91,'provenance':{'synthetic':synthetic,'run_id':rid,'stage':stage,'scenario_id':scenario},'payload':{'stage':stage,'scenario_id':scenario,'mode':mode,'attempt':activity.info().attempt}},token=ADMIN)
        eids=[ev['evidence_id']]
        if stage=='POLICY':
            pol=post_json(POLICY,'/api/policy/check',{'mode':mode,'command':policy_command,'severity':'P1','confidence':.94,'evidence_count':len(eids),'critic_validated':True,'redundancy_ok':True},token=ADMIN)
            post_json(CORE,f'/api/runs/{rid}/gates',{'stage':'POLICY','state':pol['state'],'decision':pol['decision'],'reason':pol['reason'],'evidence_ids':eids,'required_evidence':['analyst','critic','twin','observation']},token=ADMIN)
            if pol['state']!='PASS':
                return call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'GATE_BLOCKED','event_key':f'{stage}:BLOCKED','status':'BLOCKED','evidence_ids':eids,'decision':pol['decision'],'confidence':.94,'payload':pol})
        completed=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':eids,'confidence':.94,'payload':{'executor':'temporal','synthetic':synthetic,'attempt':activity.info().attempt}})
        post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':completed['version']},token=ADMIN)
        if synthetic:
            post_json(CORE,f'/api/runs/{rid}/demo-artifacts',{'artifact_type':'stage','title':stage,'sequence_no':completed['sequence'],'caption':f'{stage} — {mode} — evidence linked','payload':{'scenario_id':scenario,'synthetic':True}},token=ADMIN)
        return completed
    except Exception as exc:
        try: call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_FAILED','event_key':f'{stage}:FAIL','status':'FAIL','confidence':0,'payload':{'error':str(exc)[:500],'attempt':activity.info().attempt}})
        finally: raise
@activity.defn
async def finish_run(a): return call('POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'RESOLVE-'+a['run_id'],'command':'RESOLVE'})
@app.get('/health')
def health():return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
@app.get('/metrics')
def metrics(): return 'aiops_worker_up 1\n'
@app.post('/api/execution/start')
async def start(args:dict,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:raise HTTPException(401,'invalid internal token')
 try: policy_command_for_mode(args.get('mode') if isinstance(args,dict) else None)
 except ValueError: raise HTTPException(422,'invalid execution mode')
 c=await Client.connect(TEMP)
 try:
  h=await c.start_workflow(IncidentWorkflow.run,args,id=args['run_id'],task_queue='aiops-runner');return {'workflow_id':h.id,'run_id':args['run_id'],'executor':'temporal'}
 except WorkflowAlreadyStartedError:
  return {'workflow_id':args['run_id'],'run_id':args['run_id'],'executor':'temporal','idempotent':True}

# Terminal-only REJECT recovery. This is NOT the old claim/signal/ACK harness.
# Core #344 owns the expired eighth lease, immutable DEAD and 014/015 receipt.
# No raw lease token is accepted or placed in Temporal history.
@activity.defn(name='reject_terminal_recover')
async def reject_terminal_recover(args):
    owner=os.getenv('AIOPS_REJECT_TERMINAL_OWNER')
    if not owner:
        raise UnqualifiedTerminal('terminal_service_owner_not_configured')
    async def post(path, body):
        return await asyncio.to_thread(post_json, CORE, path, body, timeout=15, token=ADMIN)
    return await recover_terminal_once(args, owner=owner, post=post)

@app.post('/api/execution/reject-terminal')
async def start_reject_terminal(args:dict, authorization:str|None=Header(default=None)):
    if (authorization or '').removeprefix('Bearer ')!=ADMIN:
        raise HTTPException(401,'invalid internal token')
    owner=os.getenv('AIOPS_REJECT_TERMINAL_OWNER')
    if not owner:
        raise HTTPException(503,'terminal service identity not configured')
    try:
        validate_request(args, owner)
    except UnqualifiedTerminal:
        raise HTTPException(422,'unqualified terminal request')
    c=await Client.connect(TEMP)
    workflow_id=f"reject-terminal-{args['tenant_id']}-{args['event_id']}"
    try:
        h=await c.start_workflow(TerminalRejectWorkflow.run,args,id=workflow_id,
                                 task_queue='aiops-runner')
        return {'workflow_id':h.id,'run_id':args['run_id'],
                'status':'PENDING_CORE_TERMINAL','effect_allowed':False}
    except WorkflowAlreadyStartedError:
        return {'workflow_id':workflow_id,'run_id':args['run_id'],
                'idempotent':True,'effect_allowed':False}

async def worker_main():
 while True:
  try:
   c=await Client.connect(TEMP)
   async with Worker(c,task_queue='aiops-runner',workflows=[IncidentWorkflow,TerminalRejectWorkflow,AcmeSimulatedHitlWorkflow],activities=[execute_stage,start_run,finish_run,reject_terminal_recover,acme_simulated_no_effect]):await asyncio.Event().wait()
  except Exception:await asyncio.sleep(5)
@app.on_event('startup')
async def startup():asyncio.create_task(worker_main())


# The ACME simulator is NOT a human IdP/GLPI approval. This bounded route is
# disabled by default and never writes to Core, Twin, Policy, GLPI or LIVE.
# Only the simulator's nonsecret IDs enter Temporal history. The activity
# obtains fresh authenticated readbacks itself, never trusts supplied proof.
def _acme_sandbox_enabled():
    return os.getenv("AIOPS_ACME_SANDBOX_ENABLED") == "true"


def _acme_sandbox_guard():
    if not _acme_sandbox_enabled():
        raise HTTPException(503, "sandbox_capability_unavailable")


def _acme_sandbox_auth(authorization):
    if (type(authorization) is not str or not authorization.startswith("Bearer ")
            or authorization[7:] != ADMIN):
        raise HTTPException(401, "sandbox_service_denied")


@activity.defn(name="acme_simulated_no_effect")
async def acme_simulated_no_effect(intent):
    if not _acme_sandbox_enabled():
        raise SandboxDenied("sandbox_disabled")

    async def read(component, path):
        origin = {"core": CORE, "twin": TWIN, "policy": POLICY}.get(component)
        if origin is None:
            raise SandboxDenied("sandbox_component_denied")

        def fetch():
            response = requests.get(
                origin.rstrip("/") + path,
                headers={"Authorization": "Bearer " + ADMIN, "Accept": "application/json"},
                timeout=8, allow_redirects=False)
            if response.status_code != 200 or len(response.content) > 32768:
                raise SandboxDenied("sandbox_service_denied_or_unavailable")
            return response.json()

        return await asyncio.to_thread(fetch)

    return await simulate_no_effect(intent, get=read)


@app.get("/api/sandbox/acme/capabilities")
def acme_sandbox_capabilities():
    _acme_sandbox_guard()
    return capability()


@app.post("/api/sandbox/acme/e2e")
async def start_acme_simulated(intent: dict, authorization: str | None = Header(default=None)):
    _acme_sandbox_guard()
    _acme_sandbox_auth(authorization)
    try:
        validate_intent(intent)
    except SandboxDenied:
        raise HTTPException(422, "sandbox_intent_unqualified") from None
    client = await Client.connect(TEMP)
    workflow_id = "acme-simulated-" + intent["tenant_id"] + "-" + intent["attempt_id"]
    try:
        handle = await client.start_workflow(
            AcmeSimulatedHitlWorkflow.run, intent, id=workflow_id,
            task_queue="aiops-runner",
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        return {"workflow_id": handle.id, "attempt_id": intent["attempt_id"],
                "status": "PENDING_INDEPENDENT_READBACK", "effect_allowed": False}
    except WorkflowAlreadyStartedError:
        return {"workflow_id": workflow_id, "attempt_id": intent["attempt_id"],
                "idempotent": True, "effect_allowed": False}


@app.get("/api/sandbox/acme/e2e/{attempt_id}")
async def read_acme_simulated(attempt_id: str, authorization: str | None = Header(default=None)):
    _acme_sandbox_guard()
    _acme_sandbox_auth(authorization)
    # No arbitrary workflow ID, tenant or cross-sandbox lookup.
    from worker.acme_simulated_hitl import _id
    if not _id(attempt_id) or not attempt_id.startswith("ACME-SIM-"):
        raise HTTPException(404, "sandbox_receipt_unknown")
    client = await Client.connect(TEMP)
    handle = client.get_workflow_handle("acme-simulated-ACME-TEST-" + attempt_id)
    try:
        state = await handle.describe()
        if state.status != WorkflowExecutionStatus.COMPLETED:
            raise HTTPException(503, "sandbox_receipt_unqualified")
        result = await handle.result()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "sandbox_receipt_unqualified") from None
    if (type(result) is not dict
            or result.get("schema") != "aiops.worker-acme-simulated-no-effect.v1"
            or result.get("attempt_id") != attempt_id
            or result.get("tenant_id") != "ACME-TEST"
            or result.get("approval_issuer") != "TWIN_ACME_SIMULATED"
            or result.get("approval_kind") != "SIMULATED"
            or result.get("action") != "SIMULATE"
            or result.get("receipt_status") != "SIMULATED_NO_EFFECT"
            or result.get("receipt_phase") != "PRE_RESOLUTION"
            or result.get("core_status_at_validation") != "PREPARED"
            or result.get("resolution_verified") is not False
            or result.get("post_resolution_readback_required") is not True
            or result.get("audit_transitions") != [
                "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
                "TWIN_SIMULATED_APPROVAL_VALIDATED",
                "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
                "WORKER_NO_EFFECT"]
            or result.get("human_approved") is not False
            or result.get("execution_allowed") is not False
            or result.get("effect_allowed") is not False
            or result.get("real_glpi_writes_allowed") is not False
            or result.get("live_effects_allowed") is not False
            or type(result.get("effect_receipts")) is not int
            or result["effect_receipts"] != 0
            or result.get("audit_authority") != "TEMPORAL_WORKFLOW_HISTORY_ONLY"):
        raise HTTPException(503, "sandbox_receipt_unqualified")
    return result
