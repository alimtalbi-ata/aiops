import os,asyncio,datetime
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity,workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.common import RetryPolicy
from shared.http import post_json
from shared.simulation_policy_contract import policy_command_for_mode
from shared.temporal_start_history import decode_initial_start_args
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
TEMP=os.getenv('TEMPORAL_ADDRESS','aiops2-temporal:7233')
STAGES=['NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG','DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN']
RETRY=RetryPolicy(initial_interval=datetime.timedelta(seconds=1),backoff_coefficient=2.0,max_interval=datetime.timedelta(seconds=10),maximum_attempts=3)
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
        # DEMO synthetic evidence cannot qualify a real post-remediation check.
        # Stop Temporal before VERIFY PASS, reconciliation, learning or RESOLVE.
        if mode in ('DEMO', 'REPLAY', 'STORY') and stage == 'VERIFY':
            blocked = call('POST',f'{CORE}/api/runs/{rid}/events',{
                'expected_version':v,
                'stage':stage,
                'event_type':'INDEPENDENT_POSTCHECK_MISSING',
                'event_key':f'{stage}:INDEPENDENT-POSTCHECK-MISSING',
                'status':'BLOCKED',
                'decision':'HUMAN_APPROVAL',
                'confidence':0.0,
                'payload':{
                    'reason':'Synthetic observations are not independent runtime recovery proof',
                    'independent_runtime_postcheck_verified':False,
                    'actual_recovery_state':'UNKNOWN',
                    'simulation_only':True,
                    'itil_transition_authorized':False,
                    'live_remediation_authorized':False,
                },
            })
            state = call('POST',f'{CORE}/api/runs/{rid}/command',{
                'expected_version':blocked['version'],
                'idempotency_key':f'DEMO-POSTCHECK-BLOCK-{rid}',
                'command':'BLOCK',
            })
            return {'run_id':rid,'stage':stage,'status':'BLOCKED',
                    'version':state['version'],'sequence':blocked['sequence']}
        ev=post_json(EVID,'/api/evidence',{'source':f'run:{rid}:{stage.lower()}','claim':f'{stage} completed for scenario {scenario}','confidence':0.94 if stage not in ('DGX_ANALYST','DGX_CRITIC') else 0.91,'provenance':{'synthetic':synthetic,'run_id':rid,'stage':stage,'scenario_id':scenario},'payload':{'stage':stage,'scenario_id':scenario,'mode':mode,'attempt':activity.info().attempt}},token=ADMIN)
        eids=[ev['evidence_id']]
        if stage=='POLICY':
            pol=post_json(POLICY,'/api/policy/check',{'mode':mode,'command':policy_command,'severity':'P1','confidence':.94,'evidence_count':len(eids),'critic_validated':True,'redundancy_ok':True},token=ADMIN)
            post_json(CORE,f'/api/runs/{rid}/gates',{'stage':'POLICY','state':pol['state'],'decision':pol['decision'],'reason':pol['reason'],'evidence_ids':eids,'required_evidence':['analyst','critic','twin','observation']},token=ADMIN)
            if pol['state']!='PASS':
                blocked = call('POST',f'{CORE}/api/runs/{rid}/events',{
                    'expected_version':v,'stage':stage,'event_type':'GATE_BLOCKED',
                    'event_key':f'{stage}:BLOCKED','status':'BLOCKED',
                    'evidence_ids':eids,'decision':pol['decision'],
                    'confidence':0.0,'payload':pol,
                })
                state = call('POST',f'{CORE}/api/runs/{rid}/command',{
                    'expected_version':blocked['version'],
                    'idempotency_key':f'POLICY-GATE-BLOCK-{rid}',
                    'command':'BLOCK',
                })
                return {'run_id':rid,'stage':stage,'status':'BLOCKED',
                        'version':state['version'],'sequence':blocked['sequence']}
        completed=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':eids,'confidence':.94,'payload':{'executor':'temporal','synthetic':synthetic,'attempt':activity.info().attempt}})
        post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':completed['version']},token=ADMIN)
        if synthetic:
            post_json(CORE,f'/api/runs/{rid}/demo-artifacts',{'artifact_type':'stage','title':stage,'sequence_no':completed['sequence'],'caption':f'{stage} — {mode} — evidence linked','payload':{'scenario_id':scenario,'synthetic':True}},token=ADMIN)
        return {'run_id':rid,'stage':stage,'status':'PASS',
                'version':completed['version'],'sequence':completed['sequence']}
    except Exception as exc:
        try: call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_FAILED','event_key':f'{stage}:FAIL','status':'FAIL','confidence':0,'payload':{'error':str(exc)[:500],'attempt':activity.info().attempt}})
        finally: raise
@activity.defn
async def finish_run(a): return call('POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'RESOLVE-'+a['run_id'],'command':'RESOLVE'})
@workflow.defn
class IncidentWorkflow:
 @workflow.run
 async def run(self,args):
  r=await workflow.execute_activity(start_run,args,start_to_close_timeout=datetime.timedelta(seconds=30),retry_policy=RETRY)
  v=r.get('version') if isinstance(r,dict) else None
  if type(v) is not int or v < 0: raise ValueError('unqualified_start_run_version')
  for stage in STAGES:
   prior_version=v
   r=await workflow.execute_activity(execute_stage,{'stage':stage,'run_id':args['run_id'],'version':v,'mode':args['mode'],'scenario_id':args['scenario_id']},start_to_close_timeout=datetime.timedelta(seconds=60),retry_policy=RETRY)
   if (not isinstance(r,dict) or r.get('run_id')!=args['run_id']
       or r.get('stage')!=stage or r.get('status') not in ('PASS','BLOCKED')
       or type(r.get('version')) is not int or r['version']<=prior_version):
    raise ValueError('unqualified_stage_transition_receipt')
   v=r['version']
   if r['status']=='BLOCKED': return {'run_id':args['run_id'],'status':'BLOCKED','final_version':v,'blocked_stage':stage}
  f=await workflow.execute_activity(finish_run,{'run_id':args['run_id'],'version':v},start_to_close_timeout=datetime.timedelta(seconds=30),retry_policy=RETRY)
  if (not isinstance(f,dict) or f.get('status')!='RESOLVED'
      or type(f.get('version')) is not int or f['version']<=v):
   raise ValueError('unqualified_terminal_transition_receipt')
  return {'run_id':args['run_id'],'final_version':f['version'],'status':'RESOLVED'}
@app.get('/health')
def health():return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
@app.get('/metrics')
def metrics(): return 'aiops_worker_up 1\n'
@app.get('/api/execution/{run_id}/inspect')
async def inspect_execution(run_id:str,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:
  raise HTTPException(401,'invalid internal token')
 import re
 if (not isinstance(run_id,str) or not 1<=len(run_id)<=128
     or re.fullmatch(r'[A-Za-z0-9_.:-]+',run_id) is None):
  raise HTTPException(422,'invalid execution identifier')
 # Read-only lookup: no workflow start, no signal, no reset, no cancellation.
 # Workflow existence is not proof that mode/scenario/version match Core.
 try:
  c=await Client.connect(TEMP)
  h=c.get_workflow_handle(run_id)
  desc=await h.describe()
  history=await h.fetch_history()
  original_args=decode_initial_start_args(history.events)
 except Exception:
  # No reliable attestation from an unreachable or unknown Temporal service.
  raise HTTPException(503,'workflow inspection unavailable or unverified')
 return {'run_id':run_id,'workflow_id':run_id,
         'temporal_visibility':'EXISTS_UNATTESTED',
         'status_observed':str(desc.status),
         'original_start_arguments_verified':False,
         'temporal_start_history_input':original_args,
         'temporal_start_history_input_decoded':original_args is not None,
         'core_receipt_verified':False,
         'idempotent_start_confirmed':False,
         'live_remediation_authorized':False}

@app.post('/api/execution/start')
async def start(args:dict,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:raise HTTPException(401,'invalid internal token')
 if not isinstance(args,dict) or set(args) != {'run_id','mode','scenario_id','version'}:
  raise HTTPException(422,'invalid execution request shape')
 import re
 for key in ('run_id','scenario_id'):
  value=args[key]
  if (not isinstance(value,str) or not 1<=len(value)<=128
      or re.fullmatch(r'[A-Za-z0-9_.:-]+',value) is None):
   raise HTTPException(422,'invalid execution identifier')
 if type(args['version']) is not int or args['version'] < 0:
  raise HTTPException(422,'invalid execution version')
 try: policy_command_for_mode(args['mode'])
 except (ValueError,TypeError): raise HTTPException(422,'invalid execution mode')
 c=await Client.connect(TEMP)
 try:
  h=await c.start_workflow(IncidentWorkflow.run,args,id=args['run_id'],task_queue='aiops-runner');return {'workflow_id':h.id,'run_id':args['run_id'],'executor':'temporal'}
 except WorkflowAlreadyStartedError:
  # A matching workflow ID does not prove that its original mode, scenario,
  # version or Core run ownership matches this request. Never attest replay.
  raise HTTPException(409,'workflow id already exists; reconcile with Core receipt')
async def worker_main():
 from worker.int06a_registration import registered_activities
 enabled=os.getenv('AIOPS_INT06_REGISTER_NO_EFFECT','0')
 namespace=os.getenv('TEMPORAL_NAMESPACE','default') if enabled=='1' else 'default'
 activities=registered_activities([execute_stage,start_run,finish_run],
     enabled=enabled,namespace=namespace,address=TEMP)
 while True:
  try:
   c=await Client.connect(TEMP,namespace=namespace)
   async with Worker(c,task_queue='aiops-runner',workflows=[IncidentWorkflow],activities=activities):await asyncio.Event().wait()
  except Exception:await asyncio.sleep(5)
@app.on_event('startup')
async def startup():asyncio.create_task(worker_main())
