import os,asyncio,datetime
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity,workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.common import RetryPolicy
from shared.http import post_json,get_json
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
CORE=os.getenv('CORE_URL','http://aiops2-core:810');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
TEMP=os.getenv('TEMPORAL_ADDRESS','aiops2-temporal:7233');INTEL=os.getenv('INTELLIGENCE_URL','http://aiops2-intelligence:817')
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
            observed=datetime.datetime.now(datetime.timezone.utc).isoformat()
            post_json(EVID,'/api/evidence',{'source':'twin-simulator','external_id':f'{rid}:fc-errors','observed_at':observed,'claim':'Synthetic ACME scenario reports FC errors at 184 errors/min on ACME-SAN-FABRIC-A.','confidence':0.95,'provenance':{'synthetic':True,'run_id':rid,'stage':'OBSERVE','adapter':'twin-simulator','scenario_id':scenario,'observed_at':observed},'payload':{'node_id':'ACME-SAN-FABRIC-A','metric':'fc_errors','value':184,'unit':'errors/min','status':'CRITICAL','mode':mode}},token=ADMIN)
            post_json(EVID,'/api/evidence',{'source':'twin-simulator','external_id':f'{rid}:fabric-health','observed_at':observed,'claim':'Synthetic ACME scenario reports ACME-SAN-FABRIC-A degraded with health 0.42.','confidence':0.95,'provenance':{'synthetic':True,'run_id':rid,'stage':'OBSERVE','adapter':'twin-simulator','scenario_id':scenario,'observed_at':observed},'payload':{'node_id':'ACME-SAN-FABRIC-A','state':'DEGRADED','health':0.42,'mode':mode}},token=ADMIN)
        if stage in ('DGX_ANALYST','DGX_CRITIC'):
            try:
                detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
                ledger=get_json(EVID,f'/api/evidence?run_id={rid}',token=ADMIN).get('items',[])
                source_evidence=[x for x in ledger if x.get('source')!='run:'+rid+':'+stage.lower() and not str(x.get('source','')).startswith('run:'+rid+':')]
                scenario_context=get_json(CORE,f'/api/scenarios/{scenario}',token=ADMIN)
                incident={'incident_id':detail['run'].get('incident_id'),'run_id':rid,'title':scenario_context.get('name',scenario),'severity':'UNKNOWN','source':'synthetic-scenario','synthetic':mode!='LIVE'}
                if stage=='DGX_ANALYST':
                    response=post_json(INTEL,'/api/intelligence/analyze',{'incident':incident,'evidence':source_evidence,'mode':mode,'context':{'scenario':scenario_context}},timeout=50,token=ADMIN)
                    result=response['analysis']
                    saved=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'ANALYST_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':[x['evidence_id'] for x in source_evidence],'confidence':result['confidence'],'payload':{'analysis':result,'provider':'configured-openai-compatible','synthetic':mode!='LIVE','evidence_count':len(source_evidence)}})
                    post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':saved['version']},token=ADMIN)
                    return saved
                analyst_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_ANALYST' and e.get('event_type')=='ANALYST_COMPLETED'),None)
                if not analyst_event or not isinstance(analyst_event.get('payload',{}).get('analysis'),dict):
                    raise RuntimeError('analyst_result_missing')
                response=post_json(INTEL,'/api/intelligence/critic',{'incident':incident,'evidence':source_evidence,'mode':mode,'context':{'scenario':scenario_context},'analyst':analyst_event['payload']['analysis']},timeout=50,token=ADMIN)
                result=response['critique'];state='PASS' if result.get('validated') is True else 'BLOCKED'
                saved=call('POST',f'/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'CRITIC_COMPLETED','event_key':f'{stage}:COMPLETE','status':state,'evidence_ids':[x['evidence_id'] for x in source_evidence],'decision':result.get('final_recommendation'),'confidence':result.get('diagnostic_confidence',0),'payload':{'critique':result,'synthetic':mode!='LIVE','evidence_count':len(source_evidence)}})
                post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':saved['version']},token=ADMIN)
                if state=='BLOCKED':
                    blocked=call('POST',f'/api/runs/{rid}/command',{'expected_version':saved['version'],'idempotency_key':f'CRITIC-BLOCK-{rid}','command':'BLOCK'})
                    return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':blocked['version']}
                return saved
            except Exception as exc:
                blocked_event=call('POST',f'/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'INTELLIGENCE_UNAVAILABLE','event_key':f'{stage}:UNAVAILABLE','status':'BLOCKED','decision':'HUMAN_APPROVAL','confidence':0,'payload':{'reason':type(exc).__name__,'synthetic_evidence_created':False,'execution_allowed':False}})
                blocked=call('POST',f'/api/runs/{rid}/command',{'expected_version':blocked_event['version'],'idempotency_key':f'INTELLIGENCE-BLOCK-{rid}-{stage}','command':'BLOCK'})
                return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':blocked['version']}
        ev=post_json(EVID,'/api/evidence',{'source':f'run:{rid}:{stage.lower()}','claim':f'{stage} completed for scenario {scenario}','confidence':0.94,'provenance':{'synthetic':synthetic,'run_id':rid,'stage':stage,'scenario_id':scenario,'record_type':'stage_marker'},'payload':{'stage':stage,'scenario_id':scenario,'mode':mode,'attempt':activity.info().attempt}},token=ADMIN)
        eids=[ev['evidence_id']]
        if stage=='POLICY':
            detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
            analyst_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_ANALYST' and e.get('event_type')=='ANALYST_COMPLETED'),None)
            critic_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_CRITIC' and e.get('event_type')=='CRITIC_COMPLETED'),None)
            analysis=(analyst_event or {}).get('payload',{}).get('analysis',{})
            critique=(critic_event or {}).get('payload',{}).get('critique',{})
            source_ledger=get_json(EVID,f'/api/evidence?run_id={rid}',token=ADMIN).get('items',[])
            source_evidence=[x for x in source_ledger if str(x.get('source','')).startswith('twin-simulator') or not str(x.get('source','')).startswith('run:'+rid+':')]
            pol=post_json(POLICY,'/api/policy/check',{'mode':mode,'command':'EXECUTE','severity':analysis.get('severity','UNKNOWN'),'confidence':min(float(analysis.get('confidence',0)),float(critique.get('diagnostic_confidence',0))),'evidence_count':len(source_evidence),'critic_validated':critique.get('validated') is True,'redundancy_ok':False if not source_evidence else True,'evidence_fresh':bool(source_evidence),'preconditions_verified':False,'fencing_verified':False,'human_approved':False},token=ADMIN)
            post_json(CORE,f'/api/runs/{rid}/gates',{'stage':'POLICY','state':pol['state'],'decision':pol['decision'],'reason':pol['reason'],'evidence_ids':[x['evidence_id'] for x in source_evidence],'required_evidence':['analyst','critic','twin','observation']},token=ADMIN)
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
   r=await workflow.execute_activity(execute_stage,{'stage':stage,'run_id':args['run_id'],'version':v,'mode':args['mode'],'scenario_id':args['scenario_id']},start_to_close_timeout=datetime.timedelta(seconds=180),retry_policy=RETRY);v=r['version']
   if r.get('status')=='BLOCKED': return {'run_id':args['run_id'],'status':'BLOCKED','final_version':v}
  f=await workflow.execute_activity(finish_run,{'run_id':args['run_id'],'version':v},start_to_close_timeout=datetime.timedelta(seconds=30),retry_policy=RETRY);return {'run_id':args['run_id'],'final_version':f['version'],'status':f['status']}
@app.get('/health')
def health():return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
@app.get('/metrics')
def metrics(): return 'aiops_worker_up 1\n'
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
