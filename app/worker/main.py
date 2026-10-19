import os,asyncio,datetime
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity,workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.common import RetryPolicy
from shared.http import post_json
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN',os.getenv('AIOPS_ADMIN_TOKEN','Newaiops26$'));TEMP=os.getenv('TEMPORAL_ADDRESS','aiops2-temporal:7233')
STAGES=['NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG','DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN']
RETRY=RetryPolicy(initial_interval=datetime.timedelta(seconds=1),backoff_coefficient=2.0,max_interval=datetime.timedelta(seconds=10),maximum_attempts=3)
def call(method,url,payload): return post_json(url.split('/api/')[0],'/api/'+url.split('/api/',1)[1],payload,timeout=15,token=ADMIN)
@activity.defn
async def start_run(a): return call('POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'START-'+a['run_id'],'command':'START'})
@activity.defn
async def execute_stage(a):
    rid,version,stage,mode,scenario=a['run_id'],a['version'],a['stage'],a['mode'],a['scenario_id']
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
            pol=post_json(POLICY,'/api/policy/check',{'mode':mode,'command':'EXECUTE','severity':'P1','confidence':.94,'evidence_count':len(eids),'critic_validated':True,'redundancy_ok':True},token=ADMIN)
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
@workflow.defn
class IncidentWorkflow:
 @workflow.run
 async def run(self,args):
  r=await workflow.execute_activity(start_run,args,start_to_close_timeout=datetime.timedelta(seconds=30),retry_policy=RETRY);v=r['version']
  for stage in STAGES:
   r=await workflow.execute_activity(execute_stage,{'stage':stage,'run_id':args['run_id'],'version':v,'mode':args['mode'],'scenario_id':args['scenario_id']},start_to_close_timeout=datetime.timedelta(seconds=60),retry_policy=RETRY);v=r['version']
   if r.get('status')=='BLOCKED': return {'run_id':args['run_id'],'status':'BLOCKED','final_version':v}
  f=await workflow.execute_activity(finish_run,{'run_id':args['run_id'],'version':v},start_to_close_timeout=datetime.timedelta(seconds=30),retry_policy=RETRY);return {'run_id':args['run_id'],'final_version':f['version'],'status':f['status']}
@app.get('/health')
def health():return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
@app.get('/metrics')
def metrics(): return 'aiops_worker_up 1\\n'
@app.post('/api/execution/start')
async def start(args:dict,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:raise HTTPException(401,'invalid internal token')
 c=await Client.connect(TEMP)
 try:
  h=await c.start_workflow(IncidentWorkflow.run,args,id=args['run_id'],task_queue='aiops-runner');return {'workflow_id':h.id,'run_id':args['run_id'],'executor':'temporal'}
 except WorkflowAlreadyStartedError:
  return {'workflow_id':args['run_id'],'run_id':args['run_id'],'executor':'temporal','idempotent':True}
async def worker_main():
 while True:
  try:
   c=await Client.connect(TEMP)
   async with Worker(c,task_queue='aiops-runner',workflows=[IncidentWorkflow],activities=[execute_stage,start_run,finish_run]):await asyncio.Event().wait()
  except Exception:await asyncio.sleep(5)
@app.on_event('startup')
async def startup():asyncio.create_task(worker_main())
