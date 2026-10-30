import os,json,requests,datetime,hashlib,hmac,uuid
from shared.safety import canonical_sha256, gold_set_eligible, critical_approval_complete
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel,Field
from shared.db import db
from core.demo_evidence_read import register_demo_evidence_routes
from core.denial_routes import register_denial_routes
from core.critic_denial_block import block_with_denial
from core.critic_denial_resume import resume_critic_denial
from shared.ids import new
from shared.domain import transition,STAGES,initial_stage_state
from core.hitl_identity import router as hitl_identity_router
app=FastAPI(title='ACME AioOps Core',version='2.0.0')
app.include_router(hitl_identity_router)
POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813'); WORKER=os.getenv('WORKER_URL','http://aiops2-worker:815')
ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or ADMIN_TOKEN must be configured')
class RunIn(BaseModel): mode:str=Field(pattern='^(LIVE|DEMO|REPLAY|STORY)$'); scenario_id:str; incident_id:str|None=None; idempotency_key:str=Field(min_length=3,max_length=200)
class Command(BaseModel): expected_version:int; idempotency_key:str; command:str=Field(pattern='^(START|WAIT|BLOCK|RESOLVE|FAIL|CANCEL)$')
class Event(BaseModel): expected_version:int; stage:str; event_type:str; status:str; event_key:str|None=None; evidence_ids:list[str]=[]; decision:str|None=None; confidence:float|None=None; payload:dict={}
class IncidentIn(BaseModel): external_id:str; title:str; severity:str=Field(pattern='^(P1|P2|P3|P4|UNKNOWN)$'); service_id:str|None=None; source:str='simulator'; synthetic:bool=True; payload:dict={}
class ModelEvaluationIn(BaseModel):
    evaluation_id: str = Field(min_length=5,max_length=100)
    dataset_version: str = Field(min_length=1,max_length=120)
    dataset_hash: str = Field(pattern='^[a-f0-9]{64}$')
    provider: str = Field(min_length=1,max_length=160)
    model: str = Field(min_length=1,max_length=240)
    prompt_version: str = Field(min_length=1,max_length=240)
    policy_version: str = Field(min_length=1,max_length=120)
    retrieval_version: str = Field(min_length=1,max_length=120)
    sample_count: int = Field(ge=0,le=1000000)
    metrics: dict
    gate_decision: str = Field(pattern='^(PASS|FAIL|INCONCLUSIVE)$')
    artifact_uri: str|None = Field(default=None,max_length=2000)
def auth(token):
    if token!=ADMIN: raise HTTPException(401,'invalid internal token')
def bearer(authorization): return (authorization or '').removeprefix('Bearer ')
register_denial_routes(app,db,auth,bearer)
register_demo_evidence_routes(app,db,auth,bearer)
def append_event(c,rid,stage,etype,status,eids=None,decision=None,confidence=None,payload=None,event_key=None):
    if event_key:
        old=c.execute(
            'select sequence,stage,event_type,status,evidence_ids,decision,confidence,payload '
            'from aiops.run_events where run_id=%s and event_key=%s',
            (rid,event_key)
        ).fetchone()
        if old:
            def canonical(value):
                if isinstance(value,str):
                    value=json.loads(value)
                return json.dumps(value,sort_keys=True,separators=(',',':'))
            same=(
                old[1]==stage
                and old[2]==etype
                and old[3]==status
                and canonical(old[4])==canonical(eids or [])
                and old[5]==decision
                and old[6]==confidence
                and canonical(old[7])==canonical(payload or {})
            )
            if not same:
                raise ValueError('event_idempotency_conflict')
            row=c.execute(
                'select version from aiops.runs where run_id=%s',
                (rid,)
            ).fetchone()
            return old[0],row[0],True
    seq=c.execute('select coalesce(max(sequence),0)+1 from aiops.run_events where run_id=%s',(rid,)).fetchone()[0]
    c.execute('insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,status,evidence_ids,decision,confidence,payload,event_key) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(new('EVT'),rid,seq,stage,etype,status,json.dumps(eids or []),decision,confidence,json.dumps(payload or {}),event_key))
    row=c.execute('select version from aiops.runs where run_id=%s',(rid,)).fetchone()
    return seq,row[0],False
def set_stage(c,rid,stage,state,attempt=None,error=None):
    if attempt is None:
        row=c.execute('select attempt from aiops.run_stage_state where run_id=%s and stage=%s',(rid,stage)).fetchone(); attempt=(row[0] if row else 0)
    c.execute('insert into aiops.run_stage_state(run_id,stage,state,attempt,last_error) values(%s,%s,%s,%s,%s) on conflict(run_id,stage) do update set state=excluded.state,attempt=excluded.attempt,last_error=excluded.last_error,completed_at=case when excluded.state in (\'PASS\',\'BLOCKED\',\'FAIL\') then now() else aiops.run_stage_state.completed_at end,started_at=case when excluded.state=\'RUNNING\' then coalesce(aiops.run_stage_state.started_at,now()) else aiops.run_stage_state.started_at end',(rid,stage,state,attempt,error))
@app.get('/health')
def health():
    with db() as c:c.execute('select 1')
    return {'status':'ok','component':'core','authority':'canonical-run-engine'}
@app.get('/metrics')
def metrics():
    with db() as c:t,r,b,res=c.execute("select count(*),count(*) filter(where status='RUNNING'),count(*) filter(where status='BLOCKED'),count(*) filter(where status='RESOLVED') from aiops.runs").fetchone()
    return f'aiops_runs_total {t}\naiops_runs_running {r}\naiops_runs_blocked {b}\naiops_runs_resolved {res}\n'
@app.get('/api/dashboard')
def dashboard():
    with db() as c:
        stats=c.execute("select count(*),count(*) filter(where status='RUNNING'),count(*) filter(where status='BLOCKED'),count(*) filter(where status='RESOLVED'),count(*) filter(where mode='DEMO'),count(*) filter(where mode='REPLAY'),count(*) filter(where mode='STORY') from aiops.runs").fetchone()
        nodes=c.execute("select count(*),count(*) filter(where state='DEGRADED'),count(*) filter(where state='FAILED') from aiops.twin_nodes").fetchone(); incidents=c.execute("select count(*),count(*) filter(where severity='P1' and state not in('RESOLVED','CLOSED')) from aiops.incidents").fetchone()
    return {'runs_total':stats[0],'running':stats[1],'blocked':stats[2],'resolved':stats[3],'demo_runs':stats[4],'replay_runs':stats[5],'story_runs':stats[6],'twin_nodes':nodes[0],'degraded_nodes':nodes[1],'failed_nodes':nodes[2],'open_incidents':incidents[0],'open_p1':incidents[1]}
@app.post('/api/incidents')
def incident(x:IncidentIn,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    iid='INC-'+x.external_id
    with db() as c:
        c.execute('insert into aiops.incidents(incident_id,external_id,title,severity,state,service_id,opened_at,source,synthetic,payload) values(%s,%s,%s,%s,\'OPEN\',%s,now(),%s,%s,%s) on conflict(external_id) do update set title=excluded.title,severity=excluded.severity,service_id=excluded.service_id,payload=excluded.payload',(iid,x.external_id,x.title,x.severity,x.service_id,x.source,x.synthetic,json.dumps(x.payload)))
    return {'incident_id':iid,'severity':x.severity,'state':'OPEN','synthetic':x.synthetic}
@app.post('/api/runs')
def create(x:RunIn,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        row=c.execute('select run_id,mode,scenario_id,status,version from aiops.runs where idempotency_key=%s',(x.idempotency_key,)).fetchone()
        if row:return dict(zip(['run_id','mode','scenario_id','status','version'],row))
        rid=new('RUN'); c.execute('insert into aiops.runs(run_id,incident_id,mode,scenario_id,status,idempotency_key) values(%s,%s,%s,%s,%s,%s)',(rid,x.incident_id,x.mode,x.scenario_id,'CREATED',x.idempotency_key))
        for stage in STAGES:
            initial=initial_stage_state(stage)
            c.execute('insert into aiops.run_stage_state(run_id,stage,state,completed_at) values(%s,%s,%s,case when %s=\'PASS\' then now() else null end)',(rid,stage,initial,initial))
        append_event(c,rid,'INGEST','RUN_CREATED','CREATED',payload={'mode':x.mode,'scenario_id':x.scenario_id},event_key='run-created')
        return {'run_id':rid,'status':'CREATED','version':1,'mode':x.mode,'scenario_id':x.scenario_id}
@app.post('/api/runs/{rid}/command')
def command(rid:str,x:Command,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        row=c.execute('select status,version,mode from aiops.runs where run_id=%s for update',(rid,)).fetchone()
        if not row:raise HTTPException(404,'run not found')
        rec=c.execute(
            'select run_id,command,response from aiops.command_receipts '
            'where idempotency_key=%s',
            (x.idempotency_key,)
        ).fetchone()
        if rec:
            if rec[0]!=rid or rec[1]!=x.command:
                raise HTTPException(409,'command_idempotency_conflict')
            return rec[2]
        status,version,mode=row
        if version!=x.expected_version:raise HTTPException(409,'stale run version')
        target={'START':'RUNNING','WAIT':'WAITING','BLOCK':'BLOCKED','RESOLVE':'RESOLVED','FAIL':'FAILED','CANCEL':'CANCELLED'}[x.command]
        if mode=='LIVE' and x.command in ('RESOLVE','REMEDIATE'):raise HTTPException(403,'LIVE action requires verified policy/HITL path')
        try:transition(status,target)
        except ValueError as e:raise HTTPException(409,str(e))
        nv=version+1
        c.execute("update aiops.runs set status=%s,version=%s,started_at=case when %s='START' and started_at is null then now() else started_at end,completed_at=case when %s in ('RESOLVE','FAIL','CANCEL') then now() else completed_at end where run_id=%s",(target,nv,x.command,x.command,rid))
        append_event(c,rid,'RUN','STATE_TRANSITION',target,decision=x.command,payload={'mode':mode,'expected_version':version,'new_version':nv},event_key='command-'+x.idempotency_key)
        resp={'run_id':rid,'status':target,'version':nv}; c.execute('insert into aiops.command_receipts(receipt_id,run_id,idempotency_key,command,response) values(%s,%s,%s,%s,%s)',(new('RCPT'),rid,x.idempotency_key,x.command,json.dumps(resp))); return resp
@app.get('/api/runs/{rid}/critic-denial-block/receipt')
def get_critic_denial_block_receipt(
    rid:str,authorization:str|None=Header(default=None)
):
    auth(bearer(authorization))
    with db() as c:
        row=c.execute(
            'SELECT command,response FROM aiops.command_receipts '
            'WHERE run_id=%s AND idempotency_key=%s',
            (rid,'CRITIC-BLOCK-'+rid)
        ).fetchone()
        if not row:
            raise HTTPException(404,'atomic_denial_receipt_not_found')
        command,response=row
        if command!='BLOCK' or not isinstance(response,dict):
            raise HTTPException(409,'unexpected_receipt_command')
        cid=response.get('critique_id')
        if (response.get('run_id')!=rid
                or response.get('status')!='BLOCKED'
                or not response.get('denial_hash') or not cid):
            raise HTTPException(409,'atomic_denial_receipt_invalid')
        state=c.execute(
            'SELECT status,version FROM aiops.runs WHERE run_id=%s',
            (rid,)
        ).fetchone()
        intent=c.execute(
            'SELECT analysis_id,status FROM aiops.critic_denial_outbox '
            'WHERE run_id=%s AND critique_id=%s',
            (rid,cid)
        ).fetchone()
        if (not state or state[0]!='BLOCKED'
                or state[1]<response['version']
                or not intent
                or intent[1] not in ('PENDING','RECONCILED')):
            raise HTTPException(409,'atomic_denial_state_inconsistent')
        return dict(response,analysis_id=intent[0],
                    outbox_status=intent[1],
                    current_version=state[1])

@app.post('/api/runs/{rid}/critic-denial-block')
def critic_denial_block(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    required=('expected_version','idempotency_key','analysis_id',
              'critique_id','evidence_ids','policy_input')
    if any(k not in x for k in required):
        raise HTTPException(422,'critic_denial_block_missing_fields')
    try:
        with db() as c:
            return block_with_denial(
                c,rid,x['expected_version'],x['idempotency_key'],
                x['analysis_id'],x['critique_id'],x['evidence_ids'],
                x['policy_input'],transition,append_event,new
            )
    except ValueError as exc:
        raise HTTPException(409,str(exc))

@app.post('/api/runs/{rid}/critic-denial-resume')
def critic_denial_resume_endpoint(
    rid:str,authorization:str|None=Header(default=None)
):
    auth(bearer(authorization))
    try:
        with db() as c:
            return resume_critic_denial(
                c,rid,transition,append_event,new
            )
    except ValueError as exc:
        raise HTTPException(409,str(exc))


@app.post('/api/scenarios/register')
def register_scenario(x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        c.execute("insert into aiops.scenarios(scenario_id,name,seed,synthetic,description) values(%s,%s,%s,true,%s) on conflict(scenario_id) do update set name=excluded.name,seed=excluded.seed,description=excluded.description",(x['scenario_id'],x.get('name',x['scenario_id']),x.get('seed',0),x.get('description','synthetic scenario')))
    return {'scenario_id':x['scenario_id'],'synthetic':True}

@app.get('/api/scenarios')
def scenarios():
    with db() as c:r=c.execute('select scenario_id,name,seed,synthetic,description,created_at from aiops.scenarios order by scenario_id').fetchall()
    k=['scenario_id','name','seed','synthetic','description','created_at'];return {'items':[dict(zip(k,x)) for x in r]}

@app.get('/api/scenarios/{sid}')
def scenario(sid:str):
    with db() as c:
        r=c.execute('select scenario_id,name,seed,synthetic,description,created_at from aiops.scenarios where scenario_id=%s',(sid,)).fetchone()
        if not r:raise HTTPException(404,'scenario not found')
        st=c.execute('select step_no,at_seconds,action,target_node_id,payload from aiops.scenario_steps where scenario_id=%s order by step_no',(sid,)).fetchall()
    k=['scenario_id','name','seed','synthetic','description','created_at'];sk=['step_no','at_seconds','action','target_node_id','payload'];return {'scenario':dict(zip(k,r)),'steps':[dict(zip(sk,x)) for x in st]}

@app.post('/api/runs/{rid}/checkpoint')
def checkpoint(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        c.execute("insert into aiops.run_checkpoints(run_id,stage,version,workflow_id) values(%s,%s,%s,%s) on conflict(run_id) do update set stage=excluded.stage,version=excluded.version,workflow_id=coalesce(excluded.workflow_id,aiops.run_checkpoints.workflow_id),updated_at=now()",(rid,x['stage'],x['version'],x.get('workflow_id')))
    return {'run_id':rid,'stage':x['stage'],'version':x['version']}

@app.get('/api/runs/{rid}/checkpoint')
def get_checkpoint(rid:str):
    with db() as c:r=c.execute('select stage,version,workflow_id,updated_at from aiops.run_checkpoints where run_id=%s',(rid,)).fetchone()
    if not r: raise HTTPException(404,'checkpoint not found')
    return dict(zip(['stage','version','workflow_id','updated_at'],r))

@app.post('/api/runs/{rid}/demo-artifacts')
def demo_artifact(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        c.execute('insert into aiops.demo_artifacts(artifact_id,run_id,artifact_type,title,sequence_no,caption,payload) values(%s,%s,%s,%s,%s,%s,%s) on conflict(run_id,artifact_type,sequence_no) do update set title=excluded.title,caption=excluded.caption,payload=excluded.payload',(new('ART'),rid,x.get('artifact_type','story'),x.get('title',''),x.get('sequence_no',0),x.get('caption'),json.dumps(x.get('payload',{}))))
    return {'run_id':rid,'status':'PASS'}

@app.get('/api/runs/{rid}/demo-artifacts')
def demo_artifacts(rid:str):
    with db() as c:r=c.execute('select artifact_id,artifact_type,title,sequence_no,caption,payload,created_at from aiops.demo_artifacts where run_id=%s order by sequence_no',(rid,)).fetchall()
    k=['artifact_id','artifact_type','title','sequence_no','caption','payload','created_at'];return {'items':[dict(zip(k,x)) for x in r]}

@app.post('/api/runs/{rid}/execute')
def execute(rid:str,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        row=c.execute('select run_id,mode,scenario_id,version,status from aiops.runs where run_id=%s for update',(rid,)).fetchone()
        if not row: raise HTTPException(404,'run not found')
        if row[4] not in ('CREATED','WAITING'): raise HTTPException(409,f'run not executable from {row[4]}')
        existing=c.execute('select workflow_id from aiops.execution_receipts where run_id=%s',(rid,)).fetchone()
        if existing:return {'run_id':rid,'workflow_id':existing[0],'idempotent':True}
        payload={'run_id':row[0],'mode':row[1],'scenario_id':row[2],'version':row[3]}
    try:
        r=requests.post(WORKER+'/api/execution/start',json=payload,headers={'Authorization':f'Bearer {ADMIN}'},timeout=10); r.raise_for_status(); data=r.json()
        with db() as c:
            c.execute('insert into aiops.execution_receipts(run_id,workflow_id) values(%s,%s) on conflict(run_id) do nothing',(rid,data['workflow_id']))
            winner=c.execute('select workflow_id from aiops.execution_receipts where run_id=%s',(rid,)).fetchone()[0]
        data['idempotent']=bool(data.get('idempotent',False)); data['workflow_id']=winner
        return data
    except requests.RequestException as e: raise HTTPException(503,f'execution service unavailable: {e}')
@app.post('/api/runs/{rid}/events')
def add_event(rid:str,x:Event,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    if x.stage not in STAGES and x.stage!='INGEST':raise HTTPException(422,'unknown stage')
    with db() as c:
        row=c.execute('select version,status from aiops.runs where run_id=%s for update',(rid,)).fetchone()
        if not row:raise HTTPException(404,'run not found')
        # Temporal retries can arrive after a successful commit but with the
        # previous expected_version. Resolve the *same* idempotent semantic event
        # before checking its stale version; conflicting key reuse still fails.
        if x.event_key:
            previous=c.execute(
                'SELECT sequence,stage,event_type,status,evidence_ids,'
                'decision,confidence,payload FROM aiops.run_events '
                'WHERE run_id=%s AND event_key=%s',
                (rid,x.event_key)
            ).fetchone()
            if previous:
                def canonical(value):
                    if isinstance(value,str):
                        value=json.loads(value)
                    return json.dumps(value,sort_keys=True,separators=(',',':'))
                same=(
                    previous[1]==x.stage
                    and previous[2]==x.event_type
                    and previous[3]==x.status
                    and canonical(previous[4])==canonical(x.evidence_ids or [])
                    and previous[5]==x.decision
                    and previous[6]==x.confidence
                    and canonical(previous[7])==canonical(x.payload or {})
                )
                if not same:
                    raise HTTPException(409,'event_idempotency_conflict')
                return {
                    'run_id':rid,
                    'sequence':previous[0],
                    'version':row[0],
                    'idempotent':True
                }
        if row[0]!=x.expected_version:raise HTTPException(409,'stale run version')
        if x.evidence_ids:
            n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(x.evidence_ids,)).fetchone()[0]
            if n!=len(set(x.evidence_ids)):raise HTTPException(422,'unknown evidence reference')
        seq,nv,existing=append_event(c,rid,x.stage,x.event_type,x.status,x.evidence_ids,x.decision,x.confidence,x.payload,x.event_key)
        if existing: return {'run_id':rid,'sequence':seq,'version':nv,'idempotent':True}
        nv=row[0]+1
        c.execute('update aiops.runs set version=%s,overall_confidence=coalesce(%s,overall_confidence) where run_id=%s',(nv,x.confidence,rid)); set_stage(c,rid,x.stage,'PASS' if x.status=='PASS' else x.status); return {'run_id':rid,'sequence':seq,'version':nv,'idempotent':False}
@app.post('/api/runs/{rid}/gates')
def gate(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        run=c.execute('select mode from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not run: raise HTTPException(404,'run not found')
        if (x.get('stage')=='POLICY' and x.get('state')=='PASS'
                and run[0] in ('DEMO','REPLAY','STORY')
                and x.get('decision')!='SIMULATE'):
            raise HTTPException(422,'synthetic_policy_pass_requires_simulate')
        eids=x.get('evidence_ids',[]); required=x.get('required_evidence',[])
        if eids:
            n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(eids,)).fetchone()[0]
            if n!=len(set(eids)):raise HTTPException(422,'gate references unknown evidence')
        c.execute('insert into aiops.gates(gate_id,run_id,stage,state,required_evidence,evidence_ids,decision,reason) values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(run_id,stage) do update set state=excluded.state,evidence_ids=excluded.evidence_ids,decision=excluded.decision,reason=excluded.reason,evaluated_at=now()',(new('GATE'),rid,x.get('stage','UNKNOWN'),x.get('state','UNKNOWN'),json.dumps(required),json.dumps(eids),x.get('decision'),x.get('reason')))
    return {'run_id':rid,'stage':x.get('stage'),'state':x.get('state')}
@app.get('/api/runs/{rid}/gates')
def gates(rid:str):
    with db() as c:rows=c.execute('select stage,state,required_evidence,evidence_ids,decision,reason,evaluated_at from aiops.gates where run_id=%s order by evaluated_at',(rid,)).fetchall()
    k=['stage','state','required_evidence','evidence_ids','decision','reason','evaluated_at'];return {'items':[dict(zip(k,r)) for r in rows]}
@app.get('/api/incidents')
def list_incidents(limit:int=100):
    """Read-only incident registry, including incidents without runs."""
    count=max(1,min(limit,500))
    with db() as c:
        rows=c.execute(
            'select incident_id,external_id,title,severity,state,service_id,opened_at,source,synthetic '
            'from aiops.incidents order by opened_at desc limit %s',(count,)
        ).fetchall()
    fields=['incident_id','external_id','title','severity','state','service_id',
            'opened_at','source','synthetic']
    return {'items':[dict(zip(fields,row)) for row in rows], 'limit':count}


@app.get('/api/runs')
def list_runs():
    with db() as c:r=c.execute('select run_id,incident_id,mode,scenario_id,status,version,overall_confidence,created_at,started_at,completed_at from aiops.runs order by created_at desc limit 100').fetchall()
    k=['run_id','incident_id','mode','scenario_id','status','version','overall_confidence','created_at','started_at','completed_at'];return {'items':[dict(zip(k,x)) for x in r]}
@app.get('/api/runs/{rid}/evidence')
def run_evidence(rid:str):
    """Bounded read-only evidence linked to recorded events of this run."""
    with db() as c:
        if not c.execute('select 1 from aiops.runs where run_id=%s',(rid,)).fetchone():
            raise HTTPException(404,'run not found')
        rows=c.execute(
            """select distinct e.evidence_id,e.source,e.external_id,e.observed_at,
                      e.known_at,e.claim,e.confidence,e.provenance,e.payload_hash
               from aiops.evidence e
               where exists (
                 select 1 from aiops.run_events re
                 where re.run_id=%s and re.evidence_ids @> jsonb_build_array(e.evidence_id)
               ) order by e.evidence_id limit 200""",(rid,)
        ).fetchall()
    keys=['evidence_id','source','external_id','observed_at','known_at',
          'claim','confidence','provenance','payload_hash']
    return {'run_id':rid,'items':[dict(zip(keys,row)) for row in rows],
            'limit':200,'payload_excluded':True}


@app.get('/api/runs/{rid}')
def get_run(rid:str):
    with db() as c:
        r=c.execute('select run_id,incident_id,mode,scenario_id,status,version,overall_confidence,created_at,started_at,completed_at from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not r:raise HTTPException(404,'run not found')
        e=c.execute('select sequence,stage,event_type,status,occurred_at,evidence_ids,decision,confidence,payload from aiops.run_events where run_id=%s order by sequence',(rid,)).fetchall();s=c.execute('select stage,state,attempt,started_at,completed_at,last_error from aiops.run_stage_state where run_id=%s order by array_position(%s::text[],stage)',(rid,STAGES)).fetchall();g=c.execute('select stage,state,decision,reason,evidence_ids,evaluated_at from aiops.gates where run_id=%s order by evaluated_at',(rid,)).fetchall()
    k=['run_id','incident_id','mode','scenario_id','status','version','overall_confidence','created_at','started_at','completed_at'];ek=['sequence','stage','event_type','status','occurred_at','evidence_ids','decision','confidence','payload'];sk=['stage','state','attempt','started_at','completed_at','last_error'];gk=['stage','state','decision','reason','evidence_ids','evaluated_at'];return {'run':dict(zip(k,r)),'events':[dict(zip(ek,x)) for x in e],'stages':[dict(zip(sk,x)) for x in s],'gates':[dict(zip(gk,x)) for x in g]}

@app.post('/api/runs/{rid}/analysis-record')
def persist_analysis(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    analysis=x.get('analysis')
    evidence_ids=sorted(set(x.get('evidence_ids') or []))
    idem=x.get('idempotency_key')
    if not isinstance(analysis,dict) or not idem or not evidence_ids:
        raise HTTPException(422,'analysis_and_evidence_and_idempotency_key_required')
    canonical=json.dumps(evidence_ids,separators=(',',':'))
    evidence_hash=hashlib.sha256(canonical.encode()).hexdigest()
    with db() as c:
        run=c.execute('select incident_id from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not run: raise HTTPException(404,'run not found')
        existing=c.execute('select analysis_id,run_id,evidence_set_hash,provider,model,prompt_version from aiops.analysis_records where idempotency_key=%s',(idem,)).fetchone()
        if existing:
            if existing[1]!=rid: raise HTTPException(409,'analysis_idempotency_key_reused_across_runs')
            if existing[2]!=evidence_hash or existing[3]!=str(x.get('provider','unknown')) or existing[4]!=str(x.get('model','unknown')) or existing[5]!=str(x.get('prompt_version','analyst-v2.0')): raise HTTPException(409,'analysis_idempotency_key_reused_with_different_input')
            return {'analysis_id':existing[0],'idempotent':True,'evidence_set_hash':evidence_hash}
        n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(evidence_ids,)).fetchone()[0]
        if n!=len(evidence_ids): raise HTTPException(422,'analysis references unknown evidence')
        revision=c.execute('select coalesce(max(revision),0)+1 from aiops.analysis_records where run_id=%s',(rid,)).fetchone()[0]
        aid=new('ANL')
        c.execute('insert into aiops.analysis_records(analysis_id,run_id,incident_id,idempotency_key,revision,contract_version,provider,model,prompt_version,evidence_ids,evidence_set_hash,output,confidence,status) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(aid,rid,run[0],idem,revision,str(analysis.get('contract_version','2.0')),str(x.get('provider','unknown')),str(x.get('model','unknown')),str(x.get('prompt_version','analyst-v2.0')),json.dumps(evidence_ids),evidence_hash,json.dumps(analysis),float(analysis.get('confidence',0)),'VALID'))
    return {'analysis_id':aid,'revision':revision,'evidence_set_hash':evidence_hash,'idempotent':False}

@app.post('/api/runs/{rid}/critique-record')
def persist_critique(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    critique=x.get('critique'); idem=x.get('idempotency_key'); aid=x.get('analysis_id')
    evidence_ids=sorted(set(x.get('evidence_ids') or []))
    if not isinstance(critique,dict) or not idem or not aid or not evidence_ids:
        raise HTTPException(422,'critique_analysis_and_evidence_and_idempotency_key_required')
    with db() as c:
        if not c.execute('select 1 from aiops.runs where run_id=%s',(rid,)).fetchone(): raise HTTPException(404,'run not found')
        existing=c.execute('select critique_id,run_id,analysis_id,evidence_ids,provider,model from aiops.critique_records where idempotency_key=%s',(idem,)).fetchone()
        if existing:
            if existing[1]!=rid: raise HTTPException(409,'critique_idempotency_key_reused_across_runs')
            old_evidence=json.loads(existing[3]) if isinstance(existing[3],str) else existing[3]
            if existing[2]!=aid or sorted(old_evidence or [])!=evidence_ids or existing[4]!=str(x.get('provider','unknown')) or existing[5]!=str(x.get('model','unknown')): raise HTTPException(409,'critique_idempotency_key_reused_with_different_input')
            return {'critique_id':existing[0],'idempotent':True}
        if not c.execute('select 1 from aiops.analysis_records where analysis_id=%s and run_id=%s',(aid,rid)).fetchone(): raise HTTPException(422,'analysis_record_not_found_for_run')
        n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(evidence_ids,)).fetchone()[0]
        if n!=len(evidence_ids):raise HTTPException(422,'critique_references_unknown_evidence')
        cid=new('CRT')
        c.execute('insert into aiops.critique_records(critique_id,idempotency_key,analysis_id,run_id,contract_version,provider,model,validated,issues,evidence_ids,output,diagnostic_confidence) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(cid,idem,aid,rid,str(critique.get('contract_version','2.0')),str(x.get('provider','unknown')),str(x.get('model','unknown')),bool(critique.get('validated',False)),json.dumps(critique.get('issues',[])),json.dumps(evidence_ids),json.dumps(critique),float(critique.get('diagnostic_confidence',0))))
    return {'critique_id':cid,'idempotent':False}

@app.post('/api/runs/{rid}/policy-record')
def persist_policy_decision(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    policy=x.get('policy')
    if not isinstance(policy,dict): raise HTTPException(422,'policy_result_required')
    if not x.get('analysis_id') or not x.get('critique_id'): raise HTTPException(422,'analysis_and_critic_records_required')
    if policy.get('state')=='PASS':
        with db() as c:
            run=c.execute('select mode from aiops.runs where run_id=%s',(rid,)).fetchone()
            if not run: raise HTTPException(404,'run not found')
            if (run[0] in ('DEMO','REPLAY','STORY')
                    and policy.get('decision')!='SIMULATE'):
                raise HTTPException(422,'synthetic_policy_pass_requires_simulate')
            ok=c.execute("select 1 from aiops.analysis_records a join aiops.critique_records q on q.analysis_id=a.analysis_id where a.analysis_id=%s and q.critique_id=%s and a.run_id=%s and q.run_id=%s and a.status='VALID' and q.validated=true and q.output->'issues'='[]'::jsonb and q.output->'unsafe_actions'='[]'::jsonb",(x.get('analysis_id'),x.get('critique_id'),rid,rid)).fetchone()
        if not ok:raise HTTPException(409,'PASS_policy_requires_clean_validated_analysis_and_critic')
    evidence_ids=sorted(set(x.get('evidence_ids') or []))
    proof={'evidence_ids':evidence_ids,'analysis_id':x.get('analysis_id'),'critique_id':x.get('critique_id'),'policy_input':x.get('policy_input',{})}
    canonical=json.dumps({'run_id':rid,'policy':policy,'proof':proof,'policy_version':x.get('policy_version','2.1.0')},sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    with db() as c:
        if not c.execute('select 1 from aiops.runs where run_id=%s FOR UPDATE',(rid,)).fetchone(): raise HTTPException(404,'run not found')
        protected=c.execute(
            'SELECT 1 FROM aiops.critic_denial_outbox WHERE run_id=%s AND critique_id=%s',
            (rid,x.get('critique_id'))
        ).fetchone()
        if protected:
            raise HTTPException(409,'fenced_finalization_required')
        old=c.execute('select policy_decision_id from aiops.policy_decisions where run_id=%s and input_hash=%s',(rid,digest)).fetchone()
        if old:return {'policy_decision_id':old[0],'input_hash':digest,'idempotent':True}
        n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(evidence_ids,)).fetchone()[0] if evidence_ids else 0
        if n!=len(evidence_ids):raise HTTPException(422,'policy_references_unknown_evidence')
        aid=x.get('analysis_id');cid=x.get('critique_id')
        if aid and not c.execute('select 1 from aiops.analysis_records where analysis_id=%s and run_id=%s',(aid,rid)).fetchone(): raise HTTPException(422,'analysis_record_not_found_for_run')
        if cid and not c.execute('select 1 from aiops.critique_records where critique_id=%s and run_id=%s',(cid,rid)).fetchone(): raise HTTPException(422,'critique_record_not_found_for_run')
        pid=new('POL')
        decision=str(policy.get('decision','HUMAN_APPROVAL'))
        state=str(policy.get('state','UNKNOWN'))
        c.execute('insert into aiops.policy_decisions(policy_decision_id,run_id,analysis_id,critique_id,policy_version,input_hash,decision,state,reasons,proof_snapshot) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(pid,rid,aid,cid,str(x.get('policy_version','2.1.0')),digest,decision,state,json.dumps([policy.get('reason','unspecified')]),json.dumps(proof)))
    return {'policy_decision_id':pid,'input_hash':digest,'idempotent':False}


@app.get('/api/runs/{rid}/ai-ledger')
def get_ai_ledger(rid:str,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        if not c.execute('select 1 from aiops.runs where run_id=%s',(rid,)).fetchone(): raise HTTPException(404,'run not found')
        analyses=c.execute('select analysis_id,revision,contract_version,provider,model,prompt_version,evidence_ids,evidence_set_hash,output,confidence,status,created_at from aiops.analysis_records where run_id=%s order by revision',(rid,)).fetchall()
        critiques=c.execute('select critique_id,analysis_id,contract_version,provider,model,validated,issues,evidence_ids,output,diagnostic_confidence,created_at from aiops.critique_records where run_id=%s order by created_at',(rid,)).fetchall()
        decisions=c.execute('select policy_decision_id,analysis_id,critique_id,policy_version,input_hash,decision,state,reasons,proof_snapshot,created_at from aiops.policy_decisions where run_id=%s order by created_at',(rid,)).fetchall()
    return {
      'run_id':rid,
      'analyses':[dict(zip(['analysis_id','revision','contract_version','provider','model','prompt_version','evidence_ids','evidence_set_hash','output','confidence','status','created_at'],row)) for row in analyses],
      'critiques':[dict(zip(['critique_id','analysis_id','contract_version','provider','model','validated','issues','evidence_ids','output','diagnostic_confidence','created_at'],row)) for row in critiques],
      'policy_decisions':[dict(zip(['policy_decision_id','analysis_id','critique_id','policy_version','input_hash','decision','state','reasons','proof_snapshot','created_at'],row)) for row in decisions]
    }

@app.post('/api/model-evaluations')
def create_model_evaluation(x:ModelEvaluationIn,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    values=(x.evaluation_id,x.dataset_version,x.dataset_hash,x.provider,x.model,
            x.prompt_version,x.policy_version,x.retrieval_version,x.sample_count,
            json.dumps(x.metrics),x.gate_decision,x.artifact_uri)
    with db() as c:
        inserted=c.execute(
            'insert into aiops.model_evaluation_runs(evaluation_id,dataset_version,dataset_hash,provider,model,prompt_version,policy_version,retrieval_version,sample_count,metrics,gate_decision,artifact_uri) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(evaluation_id) do nothing returning evaluation_id',
            values
        ).fetchone()
        if inserted:
            return {'evaluation_id':x.evaluation_id,'gate_decision':x.gate_decision,'idempotent':False}
        prior=c.execute(
            'select dataset_version,dataset_hash,provider,model,prompt_version,policy_version,retrieval_version,sample_count,metrics,gate_decision,artifact_uri from aiops.model_evaluation_runs where evaluation_id=%s',
            (x.evaluation_id,)
        ).fetchone()
        expected=(x.dataset_version,x.dataset_hash,x.provider,x.model,x.prompt_version,
                  x.policy_version,x.retrieval_version,x.sample_count,x.metrics,
                  x.gate_decision,x.artifact_uri)
        if prior and tuple(prior)==expected:
            return {'evaluation_id':x.evaluation_id,'gate_decision':x.gate_decision,'idempotent':True}
        raise HTTPException(409,'evaluation_id_conflict')

@app.get('/api/model-evaluations')
def list_model_evaluations(limit:int=10,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    if not 1<=limit<=100: raise HTTPException(422,'invalid_evaluation_list_limit')
    with db() as c:
        rows=c.execute('select evaluation_id,dataset_version,dataset_hash,provider,model,prompt_version,policy_version,retrieval_version,sample_count,metrics,gate_decision,artifact_uri,created_at from aiops.model_evaluation_runs order by created_at desc limit %s',(limit,)).fetchall()
    fields=('evaluation_id','dataset_version','dataset_hash','provider','model','prompt_version','policy_version','retrieval_version','sample_count','metrics','gate_decision','artifact_uri','created_at')
    return {'items':[dict(zip(fields,row)) for row in rows]}

PROPOSAL_ACTION_ALLOWLIST={'COLLECT_DIAGNOSTICS','INCREASE_LOGGING','RESCAN_STORAGE','FAILOVER_PATH','ROLLBACK_CHANGE','RESTART_SERVICE','CAPACITY_EXPANSION'}
APPROVER_ROLES={
 'LOW':{'operator','senior_operator','storage_admin','oncall_lead','security_admin','incident_commander'},
 'MEDIUM':{'senior_operator','storage_admin','oncall_lead','security_admin','incident_commander'},
 'HIGH':{'storage_admin','oncall_lead','security_admin','incident_commander'},
 'CRITICAL':{'security_admin','incident_commander'},
}

@app.get('/api/proposals')
def list_action_proposals(status:str='PROPOSED',limit:int=50,authorization:str|None=Header(default=None)):
    """Authenticated read-only HITL inbox. Never grants execution authority."""
    auth(bearer(authorization))
    allowed={'PROPOSED','APPROVED','REJECTED','REVOKED','ALL'}
    if status not in allowed or not 1<=limit<=200:
        raise HTTPException(422,'invalid_proposal_filter')
    where='' if status=='ALL' else 'where p.status=%s'
    params=(limit,) if status=='ALL' else (status,limit)
    with db() as c:
        rows=c.execute(
            'select p.proposal_id,p.run_id,p.analysis_id,p.critique_id,p.source_action_id,'
            'p.proposal_revision,p.target_ci_id,p.action_type,p.risk_tier,p.parameters,'
            'p.evidence_ids,p.preconditions,p.expected_postconditions,p.rollback_plan,'
            'p.proposal_hash,p.status,p.expires_at '
            'from aiops.action_proposals p '+where+
            ' order by p.expires_at asc limit %s',params
        ).fetchall()
        items=[]
        for row in rows:
            keys=('proposal_id','run_id','analysis_id','critique_id','source_action_id',
                  'revision','target_ci_id','action_type','risk_tier','parameters',
                  'evidence_ids','preconditions','expected_postconditions','rollback_plan',
                  'proposal_hash','status','expires_at')
            item=dict(zip(keys,row))
            approvals=c.execute(
                'select approval_id,actor_id,actor_role,decision,decided_at,expires_at '
                'from aiops.approval_records where proposal_id=%s '
                'order by decided_at',(item['proposal_id'],)
            ).fetchall()
            item['approvals']=[dict(zip(
                ('approval_id','actor_id','actor_role','decision','decided_at','expires_at'),a
            )) for a in approvals]
            item['execution_allowed']=False
            items.append(item)
    return {'items':items,'count':len(items),'status_filter':status,
            'execution_allowed':False,'authority':'read-only-hitl-inbox'}


@app.post('/api/runs/{rid}/proposals')
def create_action_proposal(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    target=str(x.get('target_ci_id','')).strip()
    action=str(x.get('action_type','')).strip().upper()
    risk=str(x.get('risk_tier','')).strip().upper()
    source_action_id=str(x.get('source_action_id','')).strip()
    analysis_id=str(x.get('analysis_id','')).strip()
    critique_id=str(x.get('critique_id','')).strip()
    evidence_ids=sorted(set(x.get('evidence_ids') or []))
    preconditions=x.get('preconditions') or []
    postconditions=x.get('expected_postconditions') or []
    parameters=x.get('parameters') or {}
    rollback=x.get('rollback_plan') or {}
    if not target or action not in PROPOSAL_ACTION_ALLOWLIST or risk not in APPROVER_ROLES:
        raise HTTPException(422,'invalid_target_action_or_risk_tier')
    if not source_action_id or not analysis_id or not critique_id:
        raise HTTPException(422,'validated_analysis_critic_and_source_action_required')
    if not evidence_ids or not preconditions or not postconditions:
        raise HTTPException(422,'evidence_preconditions_and_expected_postconditions_required')
    if risk in ('HIGH','CRITICAL') and not rollback:
        raise HTTPException(422,'rollback_plan_required_for_high_risk_action')
    canonical={'run_id':rid,'analysis_id':analysis_id,'critique_id':critique_id,'source_action_id':source_action_id,'target_ci_id':target,'action_type':action,'risk_tier':risk,'parameters':parameters,'evidence_ids':evidence_ids,'preconditions':preconditions,'expected_postconditions':postconditions,'rollback_plan':rollback}
    digest=canonical_sha256(canonical)
    with db() as c:
        run=c.execute('select mode from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not run:raise HTTPException(404,'run not found')
        records=c.execute('select a.output,a.evidence_ids,a.status,c.validated,c.evidence_ids,c.output from aiops.analysis_records a join aiops.critique_records c on c.analysis_id=a.analysis_id where a.analysis_id=%s and a.run_id=%s and c.critique_id=%s and c.run_id=%s',(analysis_id,rid,critique_id,rid)).fetchone()
        if not records or records[2]!='VALID' or records[3] is not True:raise HTTPException(409,'validated_analysis_and_critic_required')
        analysis_output=json.loads(records[0]) if isinstance(records[0],str) else records[0]
        analysis_evidence=json.loads(records[1]) if isinstance(records[1],str) else records[1]
        critique_evidence=json.loads(records[4]) if isinstance(records[4],str) else records[4]
        critique_output=json.loads(records[5]) if isinstance(records[5],str) else records[5]
        source_action=next((a for a in analysis_output.get('recommended_actions',[]) if a.get('action_id')==source_action_id),None)
        if not source_action:raise HTTPException(422,'source_action_not_in_validated_analysis')
        if source_action.get('advisory_only') is not True or source_action.get('requires_human_approval') is not True:raise HTTPException(422,'source_action_is_not_advisory_only')
        if critique_output.get('issues') or critique_output.get('unsafe_actions'):raise HTTPException(409,'critic_issues_or_unsafe_actions_prevent_proposal')
        if source_action.get('risk_tier')!=risk:raise HTTPException(422,'proposal_risk_must_match_analyst_action')
        if source_action.get('target_ci_id') and source_action.get('target_ci_id')!=target:raise HTTPException(422,'proposal_target_must_match_analyst_action')
        if not set(evidence_ids).issubset(set(analysis_evidence)) or not set(evidence_ids).issubset(set(critique_evidence)):
            raise HTTPException(422,'proposal_evidence_must_be_in_analysis_and_critic_scope')
        n=c.execute('select count(*) from aiops.evidence where evidence_id=any(%s)',(evidence_ids,)).fetchone()[0]
        if n!=len(evidence_ids):raise HTTPException(422,'proposal_references_unknown_evidence')
        old=c.execute('select proposal_id,proposal_revision,status from aiops.action_proposals where run_id=%s and proposal_hash=%s',(rid,digest)).fetchone()
        if old:return {'proposal_id':old[0],'revision':old[1],'status':old[2],'proposal_hash':digest,'idempotent':True,'execution_allowed':False}
        revision=c.execute('select coalesce(max(proposal_revision),0)+1 from aiops.action_proposals where run_id=%s',(rid,)).fetchone()[0]
        pid=new('ACT')
        expires=x.get('expires_at')
        if expires:
            try: expires=datetime.datetime.fromisoformat(str(expires).replace('Z','+00:00'))
            except ValueError: raise HTTPException(422,'expires_at_must_be_iso8601')
            if expires.tzinfo is None:raise HTTPException(422,'expires_at_requires_timezone')
            if expires<=datetime.datetime.now(datetime.timezone.utc):raise HTTPException(422,'proposal_expiry_must_be_future')
        else: expires=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)
        c.execute('insert into aiops.action_proposals(proposal_id,run_id,analysis_id,critique_id,source_action_id,proposal_revision,target_ci_id,action_type,risk_tier,parameters,evidence_ids,preconditions,expected_postconditions,rollback_plan,proposal_hash,status,expires_at) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(pid,rid,analysis_id,critique_id,source_action_id,revision,target,action,risk,json.dumps(parameters),json.dumps(evidence_ids),json.dumps(preconditions),json.dumps(postconditions),json.dumps(rollback),digest,'PROPOSED',expires))
    return {'proposal_id':pid,'revision':revision,'proposal_hash':digest,'status':'PROPOSED','expires_at':expires.isoformat(),'execution_allowed':False,'idempotent':False}

@app.post('/api/proposals/{proposal_id}/approval')
def record_proposal_approval(proposal_id:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    supplied_hash=str(x.get('proposal_hash',''))
    actor=str(x.get('actor_id','')).strip()
    role=str(x.get('actor_role','')).strip().lower()
    decision=str(x.get('decision','')).strip().upper()
    nonce=str(x.get('nonce','')).strip()
    scope=x.get('scope') or {}
    requested_revoke_id=str(x.get('approval_id_to_revoke','')).strip() if decision=='REVOKE' else None
    if not actor or not role or decision not in ('APPROVE','REJECT','REVOKE') or not nonce or not supplied_hash:
        raise HTTPException(422,'actor_role_decision_nonce_and_proposal_hash_required')
    if decision=='REVOKE' and not requested_revoke_id:
        raise HTTPException(422,'approval_id_to_revoke_required')
    with db() as c:
        p=c.execute('select p.run_id,r.mode,p.target_ci_id,p.action_type,p.risk_tier,p.proposal_hash,p.status,p.expires_at,p.proposal_revision from aiops.action_proposals p join aiops.runs r on r.run_id=p.run_id where p.proposal_id=%s for update of p',(proposal_id,)).fetchone()
        if not p:raise HTTPException(404,'proposal not found')
        rid,run_mode,target,action,risk,digest,status,expires,proposal_revision=p
        if run_mode!='LIVE':raise HTTPException(403,'synthetic_mode_cannot_authorize_real_approval')
        if not hmac.compare_digest(supplied_hash,digest):raise HTTPException(409,'proposal_hash_mismatch')
        expected_scope={'proposal_hash':digest,'target_ci_id':target,'action_type':action}
        if scope!=expected_scope:raise HTTPException(422,'approval_scope_must_match_exact_proposal')
        old=c.execute('select approval_id,proposal_id,proposal_hash,decision,actor_id,actor_role,scope,audit from aiops.approval_records where nonce=%s',(nonce,)).fetchone()
        if old:
            old_scope=json.loads(old[6]) if isinstance(old[6],str) else old[6]
            old_audit=json.loads(old[7]) if isinstance(old[7],str) else old[7]
            if old[1]==proposal_id and old[2]==digest and old[3]==decision and old[4]==actor and old[5]==role and old_scope==scope and old_audit.get('revokes_approval_id')==requested_revoke_id:
                return {'approval_id':old[0],'proposal_id':proposal_id,'decision':decision,'idempotent':True,'execution_allowed':False}
            raise HTTPException(409,'approval_nonce_reuse')
        if decision=='REVOKE':
            if status!='APPROVED':raise HTTPException(409,'only_approved_proposals_can_be_revoked')
            revocable=c.execute("select approval_id from aiops.approval_records where approval_id=%s and proposal_id=%s and proposal_hash=%s and decision='APPROVE' and expires_at>now()",(requested_revoke_id,proposal_id,digest)).fetchone()
            if not revocable:raise HTTPException(409,'active_approval_to_revoke_not_found')
        elif status!='PROPOSED':
            raise HTTPException(409,'proposal_not_approvable')
        if expires<=datetime.datetime.now(datetime.timezone.utc):raise HTTPException(409,'proposal_expired')
        if role not in APPROVER_ROLES[risk]:raise HTTPException(403,'role_not_authorized_for_risk_tier')
        prior=c.execute("select actor_id,actor_role from aiops.approval_records where proposal_id=%s and decision='APPROVE' and expires_at>now() order by decided_at",(proposal_id,)).fetchall()
        if decision=='APPROVE' and risk=='CRITICAL':
            if any(row[0]==actor or row[1]==role for row in prior):raise HTTPException(409,'critical_action_requires_two_distinct_actors_and_roles')
        approval_id=new('APR')
        audit={'run_id':rid,'source':'human-in-the-loop-api'}
        if requested_revoke_id:audit['revokes_approval_id']=requested_revoke_id
        c.execute('insert into aiops.approval_records(approval_id,proposal_id,proposal_hash,actor_id,actor_role,decision,scope,nonce,expires_at,audit) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(approval_id,proposal_id,digest,actor,role,decision,json.dumps(scope),nonce,expires,json.dumps(audit)))
        approval_count=(len(prior)+1) if decision=='APPROVE' else 0
        approval_complete=(decision=='APPROVE' and (risk!='CRITICAL' or (approval_count>=2 and critical_approval_complete({row[1] for row in prior}|{role}))))
        next_status=('REJECTED' if decision=='REJECT' else ('REVOKED' if decision=='REVOKE' else ('APPROVED' if approval_complete else 'PROPOSED')))
        if next_status!=status:
            c.execute('update aiops.action_proposals set status=%s where proposal_id=%s',(next_status,proposal_id))
        if next_status in ('APPROVED','REJECTED','REVOKED'):
            delivery_decision='APPROVE' if next_status=='APPROVED' else 'REJECT'
            c.execute(
                'insert into aiops.hitl_decision_outbox '
                '(event_id,proposal_id,run_id,proposal_hash,proposal_revision,decision,source_status,approval_id) '
                'values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict '
                '(proposal_id,proposal_hash,proposal_revision,decision) do nothing',
                (new('HDO'),proposal_id,rid,digest,proposal_revision,
                 delivery_decision,next_status,approval_id)
            )
    return {'approval_id':approval_id,'proposal_id':proposal_id,'decision':decision,'proposal_hash':digest,'approval_count':approval_count,'approval_complete':approval_complete,'status':next_status,'execution_allowed':False,'idempotent':False}

@app.post('/api/hitl/decision-outbox/claim')
def claim_hitl_decision_outbox(x:dict,authorization:str|None=Header(default=None)):
    """Lease committed Core decisions for at-least-once Temporal notification."""
    auth(bearer(authorization))
    owner=str(x.get('owner','')).strip()
    limit=x.get('limit',20)
    lease_seconds=x.get('lease_seconds',45)
    if not owner or len(owner)>128 or type(limit) is not int or not 1<=limit<=100:
        raise HTTPException(422,'invalid_outbox_claim_owner_or_limit')
    if type(lease_seconds) is not int or not 15<=lease_seconds<=300:
        raise HTTPException(422,'invalid_outbox_lease_duration')
    with db() as c:
        c.execute(
            "update aiops.hitl_decision_outbox set status='DEAD',"
            "lease_owner=null,lease_token=null,lease_until=null,"
            "last_error='delivery_attempt_limit_exceeded' "
            "where status='LEASED' and lease_until<=now() and attempts>=20"
        )
        candidates=c.execute(
            "select event_id from aiops.hitl_decision_outbox "
            "where attempts<20 and ((status='PENDING' and available_at<=now()) "
            "or (status='LEASED' and lease_until<=now())) "
            "order by created_at for update skip locked limit %s",
            (limit,)
        ).fetchall()
        items=[]
        for (event_id,) in candidates:
            lease_token=uuid.uuid4().hex
            row=c.execute(
                "update aiops.hitl_decision_outbox set status='LEASED',"
                "lease_owner=%s,lease_token=%s,"
                "lease_until=now()+(%s * interval '1 second'),attempts=attempts+1 "
                "where event_id=%s returning event_id,proposal_id,run_id,"
                "proposal_hash,proposal_revision,decision,source_status,lease_token,attempts",
                (owner,lease_token,lease_seconds,event_id)
            ).fetchone()
            if row:
                items.append(dict(zip(
                    ('event_id','proposal_id','run_id','proposal_hash',
                     'proposal_revision','decision','source_status','lease_token','attempts'),
                    row
                )))
    return {'items':items,'count':len(items),'delivery':'at-least-once',
            'execution_allowed':False}


@app.post('/api/hitl/decision-outbox/{event_id}/delivered')
def acknowledge_hitl_decision_outbox(event_id:str,x:dict,authorization:str|None=Header(default=None)):
    """Acknowledge only the active lease after Temporal accepted the signal."""
    auth(bearer(authorization))
    token=str(x.get('lease_token','')).strip()
    if not token:
        raise HTTPException(422,'outbox_lease_token_required')
    with db() as c:
        row=c.execute(
            'select status,lease_token from aiops.hitl_decision_outbox '
            'where event_id=%s for update',(event_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404,'outbox_event_not_found')
        if row[0]=='DELIVERED':
            return {'event_id':event_id,'status':'DELIVERED','idempotent':True}
        if row[0]!='LEASED' or not row[1] or not hmac.compare_digest(str(row[1]),token):
            raise HTTPException(409,'outbox_lease_lost_or_invalid')
        c.execute(
            "update aiops.hitl_decision_outbox set status='DELIVERED',"
            "delivered_at=now(),lease_owner=null,lease_token=null,lease_until=null,last_error=null "
            "where event_id=%s",(event_id,)
        )
    return {'event_id':event_id,'status':'DELIVERED','idempotent':False}


@app.get('/api/hitl/decision-outbox/status')
def hitl_decision_outbox_status(authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        rows=c.execute(
            'select status,count(*) from aiops.hitl_decision_outbox group by status order by status'
        ).fetchall()
    return {'counts':{status:count for status,count in rows},
            'delivery':'at-least-once','execution_allowed':False}


@app.post('/api/runs/{rid}/learning-cases')
def create_learning_case(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    idem=str(x.get('idempotency_key','')).strip()
    case_type=str(x.get('case_type','INCIDENT')).upper()
    label=x.get('label') or {}
    evidence_ids=sorted(set(x.get('evidence_ids') or []))
    human_reviewed=bool(x.get('human_reviewed',False))
    outcome_verified=bool(x.get('outcome_verified',False))
    gold_eligible=bool(x.get('gold_eligible',False))
    reviewer=str(x.get('reviewed_by','')).strip()
    review_note=str(x.get('review_note','')).strip()
    if not idem or case_type not in ('INCIDENT','PROBLEM','CHANGE','REMEDIATION','FALSE_POSITIVE','NEAR_MISS') or not evidence_ids:
        raise HTTPException(422,'idempotency_case_type_and_evidence_required')
    if human_reviewed and (not reviewer or not review_note):raise HTTPException(422,'reviewer_identity_and_review_note_required')
    with db() as c:
        run=c.execute('select mode from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not run:raise HTTPException(404,'run not found')
        rows=c.execute("select evidence_id,coalesce(provenance->>'synthetic','unknown') from aiops.evidence where evidence_id=any(%s)",(evidence_ids,)).fetchall()
        if len(rows)!=len(evidence_ids):raise HTTPException(422,'learning_case_references_unknown_evidence')
        synthetic=(run[0]!='LIVE') or any(flag.lower()!='false' for _,flag in rows)
        verification_id=x.get('verification_id')
        if outcome_verified:
            if not verification_id:raise HTTPException(422,'verified_outcome_requires_verification_id')
            vr=c.execute("select outcome from aiops.verification_records where verification_id=%s and outcome='PASS'",(verification_id,)).fetchone()
            if not vr:raise HTTPException(422,'verified_outcome_requires_passed_verification_record')
        if gold_eligible and not gold_set_eligible(run[0],synthetic,human_reviewed,outcome_verified):
            raise HTTPException(422,'gold_set_requires_live_non_synthetic_human_review_and_verified_outcome')
        old=c.execute('select learning_case_id,gold_eligible,source_run_id,case_type,evidence_ids,label,human_reviewed,outcome_verified,synthetic,analysis_id,critique_id,verification_id,exclusion_reasons,reviewed_by,review_note from aiops.learning_cases where idempotency_key=%s',(idem,)).fetchone()
        if old:
            if old[2]!=rid: raise HTTPException(409,'learning_idempotency_key_reused_across_runs')
            old_evidence=json.loads(old[4]) if isinstance(old[4],str) else old[4]
            old_label=json.loads(old[5]) if isinstance(old[5],str) else old[5]
            old_exclusions=json.loads(old[12]) if isinstance(old[12],str) else old[12]
            if old[1]!=gold_eligible or old[3]!=case_type or sorted(old_evidence or [])!=evidence_ids or old_label!=label or old[6]!=human_reviewed or old[7]!=outcome_verified or old[8]!=synthetic or old[9]!=x.get('analysis_id') or old[10]!=x.get('critique_id') or old[11]!=verification_id or old_exclusions!=(x.get('exclusion_reasons') or []) or old[13]!=(reviewer or None) or old[14]!=(review_note or None):
                raise HTTPException(409,'learning_idempotency_key_reused_with_different_input')
            return {'learning_case_id':old[0],'gold_eligible':old[1],'idempotent':True}
        for field,table in [('analysis_id','analysis_records'),('critique_id','critique_records')]:
            ref=x.get(field)
            if ref and not c.execute(f'select 1 from aiops.{table} where {field}=%s and run_id=%s',(ref,rid)).fetchone():
                raise HTTPException(422,f'{field}_not_found_for_run')
        revision=c.execute('select coalesce(max(revision),0)+1 from aiops.learning_cases where source_run_id=%s',(rid,)).fetchone()[0]
        case_id=new('LRN')
        c.execute('insert into aiops.learning_cases(learning_case_id,idempotency_key,source_run_id,revision,case_type,synthetic,human_reviewed,outcome_verified,gold_eligible,label,evidence_ids,analysis_id,critique_id,verification_id,exclusion_reasons,reviewed_at,reviewed_by,review_note) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(case_id,idem,rid,revision,case_type,synthetic,human_reviewed,outcome_verified,gold_eligible,json.dumps(label),json.dumps(evidence_ids),x.get('analysis_id'),x.get('critique_id'),verification_id,json.dumps(x.get('exclusion_reasons') or []),datetime.datetime.now(datetime.timezone.utc) if human_reviewed else None,reviewer or None,review_note or None))
    return {'learning_case_id':case_id,'revision':revision,'synthetic':synthetic,'gold_eligible':gold_eligible,'execution_allowed':False,'idempotent':False}

# V2.7 denial intent journal. Only a rejected Critic can be recorded.
@app.post('/api/runs/{rid}/denial-intent')
def record_denial_intent(rid:str,x:dict,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    aid=x.get('analysis_id'); cid=x.get('critique_id')
    ids=x.get('evidence_ids'); policy_input=x.get('policy_input')
    if not aid or not cid or not isinstance(ids,list) or not ids or not isinstance(policy_input,dict):
        raise HTTPException(422,'denial_intent_requires_ledger_and_evidence')
    ids=sorted(set(ids))
    if policy_input.get('critic_validated') is not False or policy_input.get('command')!='EXECUTE':
        raise HTTPException(422,'denial_intent_must_be_rejected_critic')
    with db() as c:
        locked=c.execute(
            'SELECT status FROM aiops.runs WHERE run_id=%s FOR UPDATE',
            (rid,)
        ).fetchone()
        if not locked:
            raise HTTPException(404,'run_not_found')
        valid=c.execute("""
            SELECT 1 FROM aiops.critique_records q
            JOIN aiops.analysis_records a ON a.analysis_id=q.analysis_id
            WHERE q.critique_id=%s AND q.run_id=%s AND q.analysis_id=%s
              AND a.run_id=%s AND q.validated=false
        """,(cid,rid,aid,rid)).fetchone()
        if not valid:raise HTTPException(409,'critic_denial_not_verified')
        present=c.execute('SELECT count(*) FROM aiops.evidence WHERE evidence_id=any(%s)',(ids,)).fetchone()[0]
        if present!=len(ids):raise HTTPException(422,'unknown_evidence')
        inserted=c.execute("""
            INSERT INTO aiops.critic_denial_outbox
              (run_id,critique_id,analysis_id,evidence_ids,policy_input)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (run_id, critique_id) DO NOTHING
            RETURNING run_id
        """,(rid,cid,aid,ids,json.dumps(policy_input))).fetchone()
        if inserted:
            return {'run_id':rid,'critique_id':cid,'status':'PENDING','idempotent':False}
        old=c.execute('SELECT analysis_id,evidence_ids,policy_input,status FROM aiops.critic_denial_outbox WHERE run_id=%s AND critique_id=%s',(rid,cid)).fetchone()
        if not old or old[0]!=aid or sorted(old[1])!=ids or old[2]!=policy_input:
            raise HTTPException(409,'denial_intent_conflict')
        return {'run_id':rid,'critique_id':cid,'status':old[3],'idempotent':True}


@app.get('/api/denial-intents/pending')
def pending_denial_intents(limit:int=20,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    if not 1<=limit<=50:raise HTTPException(422,'invalid_limit')
    with db() as c:
        rows=c.execute("""
            SELECT o.run_id,o.critique_id,o.analysis_id,o.evidence_ids,o.policy_input
            FROM aiops.critic_denial_outbox o JOIN aiops.runs r ON r.run_id=o.run_id
            WHERE o.status='PENDING' AND r.status='BLOCKED'
            ORDER BY o.created_at LIMIT %s
        """,(limit,)).fetchall()
    return {'items':[dict(zip(['run_id','critique_id','analysis_id','evidence_ids','policy_input'],r)) for r in rows]}


@app.post('/api/runs/{rid}/denial-intent/{cid}/reconciled')
def reconcile_denial_intent(rid:str,cid:str,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    raise HTTPException(409,'fenced_finalization_required')
