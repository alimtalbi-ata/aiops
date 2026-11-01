import os,json,requests,datetime,hmac,re
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from shared.db import db
from shared.ids import new
from shared.domain import transition,STAGES
from shared.tenant_scope import reject_unqualified_tenant_scope
from shared.demo_policy_gate_read_model import project_demo_policy_gate
from core.itsm_xref import router as itsm_xref_router
from core.hitl_reject_delivery import router as hitl_reject_delivery_router
app=FastAPI(title='ACME AioOps Core',version='2.0.0')
app.include_router(itsm_xref_router)
# Core owns the REJECT-only terminal route; Worker may not mutate the outbox.
app.include_router(hitl_reject_delivery_router)
POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813'); WORKER=os.getenv('WORKER_URL','http://aiops2-worker:815')
ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or ADMIN_TOKEN must be configured')
class RunIn(BaseModel): mode:str=Field(pattern='^(LIVE|DEMO|REPLAY|STORY)$'); scenario_id:str; incident_id:str|None=None; idempotency_key:str=Field(min_length=3,max_length=200)
class Command(BaseModel): expected_version:int; idempotency_key:str; command:str=Field(pattern='^(START|WAIT|BLOCK|RESOLVE|FAIL|CANCEL)$')
class Event(BaseModel): expected_version:int; stage:str; event_type:str; status:str; event_key:str|None=None; evidence_ids:list[str]=[]; decision:str|None=None; confidence:float|None=None; payload:dict={}
class IncidentIn(BaseModel): external_id:str; title:str; severity:str=Field(pattern='^(P1|P2|P3|P4|UNKNOWN)$'); service_id:str|None=None; source:str='simulator'; synthetic:bool=True; payload:dict={}
def auth(token):
    if token!=ADMIN: raise HTTPException(401,'invalid internal token')
def bearer(authorization): return (authorization or '').removeprefix('Bearer ')
def append_event(c,rid,stage,etype,status,eids=None,decision=None,confidence=None,payload=None,event_key=None):
    if event_key:
        old=c.execute('select sequence from aiops.run_events where run_id=%s and event_key=%s',(rid,event_key)).fetchone()
        if old:
            row=c.execute('select version from aiops.runs where run_id=%s',(rid,)).fetchone()
            return old[0],row[0],True
    seq=c.execute('select coalesce(max(sequence),0)+1 from aiops.run_events where run_id=%s',(rid,)).fetchone()[0]
    c.execute('insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,status,evidence_ids,decision,confidence,payload,event_key) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(new('EVT'),rid,seq,stage,etype,status,json.dumps(eids or []),decision,confidence,json.dumps(payload or {}),event_key))
    row=c.execute('select version from aiops.runs where run_id=%s',(rid,)).fetchone()
    return seq,row[0],False
def set_stage(c,rid,stage,state,attempt=None,error=None):
    if attempt is None:
        c.execute('select attempt from aiops.run_stage_state where run_id=%s and stage=%s',(rid,stage)); row=c.fetchone(); attempt=(row[0] if row else 0)
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
        for stage in STAGES:c.execute('insert into aiops.run_stage_state(run_id,stage,state) values(%s,%s,\'PENDING\')',(rid,stage))
        append_event(c,rid,'INGEST','RUN_CREATED','CREATED',payload={'mode':x.mode,'scenario_id':x.scenario_id},event_key='run-created')
        return {'run_id':rid,'status':'CREATED','version':1,'mode':x.mode,'scenario_id':x.scenario_id}
@app.post('/api/runs/{rid}/command')
def command(rid:str,x:Command,authorization:str|None=Header(default=None)):
    auth(bearer(authorization))
    with db() as c:
        row=c.execute('select status,version,mode from aiops.runs where run_id=%s for update',(rid,)).fetchone()
        if not row:raise HTTPException(404,'run not found')
        rec=c.execute('select run_id,command,response from aiops.command_receipts where idempotency_key=%s',(x.idempotency_key,)).fetchone()
        if rec:
            if rec[0]!=rid or rec[1]!=x.command:
                raise HTTPException(409,'idempotency key bound to another command or Run')
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
        # Check the existing keyed event BEFORE the version fence: an exact
        # retry is safe even after the first request advanced the Run version.
        # A key cannot silently authorize different event content.
        if x.event_key:
            previous=c.execute(
                'select sequence,stage,event_type,status,evidence_ids,decision,confidence,payload '
                'from aiops.run_events where run_id=%s and event_key=%s',
                (rid,x.event_key)).fetchone()
            if previous:
                seq,stage,etype,status,eids,decision,confidence,payload=previous
                if (stage!=x.stage or etype!=x.event_type or status!=x.status
                        or eids!=x.evidence_ids or decision!=x.decision
                        or (float(confidence) if confidence is not None else None)!=x.confidence
                        or payload!=x.payload):
                    raise HTTPException(409,'event key bound to different content')
                return {'run_id':rid,'sequence':seq,'version':row[0],'idempotent':True}
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
        if not c.execute('select 1 from aiops.runs where run_id=%s',(rid,)).fetchone(): raise HTTPException(404,'run not found')
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
@app.get('/api/runs')
def list_runs():
    with db() as c:r=c.execute('select run_id,incident_id,mode,scenario_id,status,version,overall_confidence,created_at,started_at,completed_at from aiops.runs order by created_at desc limit 100').fetchall()
    k=['run_id','incident_id','mode','scenario_id','status','version','overall_confidence','created_at','started_at','completed_at'];return {'items':[dict(zip(k,x)) for x in r]}
@app.get('/api/runs/{rid}')
def get_run(rid:str):
    with db() as c:
        r=c.execute('select run_id,incident_id,mode,scenario_id,status,version,overall_confidence,created_at,started_at,completed_at from aiops.runs where run_id=%s',(rid,)).fetchone()
        if not r:raise HTTPException(404,'run not found')
        e=c.execute('select sequence,stage,event_type,status,occurred_at,evidence_ids,decision,confidence,payload from aiops.run_events where run_id=%s order by sequence',(rid,)).fetchall();s=c.execute('select stage,state,attempt,started_at,completed_at,last_error from aiops.run_stage_state where run_id=%s order by array_position(%s::text[],stage)',(rid,STAGES)).fetchall();g=c.execute('select stage,state,decision,reason,evidence_ids,evaluated_at from aiops.gates where run_id=%s order by evaluated_at',(rid,)).fetchall()
    k=['run_id','incident_id','mode','scenario_id','status','version','overall_confidence','created_at','started_at','completed_at'];ek=['sequence','stage','event_type','status','occurred_at','evidence_ids','decision','confidence','payload'];sk=['stage','state','attempt','started_at','completed_at','last_error'];gk=['stage','state','decision','reason','evidence_ids','evaluated_at'];return {'run':dict(zip(k,r)),'events':[dict(zip(ek,x)) for x in e],'stages':[dict(zip(sk,x)) for x in s],'gates':[dict(zip(gk,x)) for x in g]}


# Read-only, internal-only synthetic Core projection for the signed NOC join.
# This is NOT tenant authorization or runtime observation. Existing legacy Core
# read endpoints are outside this incremental boundary and remain unqualified.
_NOC_CORE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
_NOC_CORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
                     "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def _noc_core_response(content, status_code=200, headers=None):
    return JSONResponse(content, status_code=status_code,
                        headers={**_NOC_CORE_HEADERS, **(headers or {})})


def _noc_core_auth_failure(authorization: str | None):
    """Use the same internal-only bearer fence for both synthetic Core reads."""
    secret = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    if (not isinstance(secret, str) or len(secret) < 32 or len(secret) > 256
            or not secret.isascii() or any(c.isspace() for c in secret)):
        return _noc_core_response({"detail": "noc_core_auth_not_configured"}, 503)
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator or not supplied
            or not hmac.compare_digest(supplied, secret)):
        return _noc_core_response({"detail": "invalid_noc_core_token"}, 401,
                                  {"WWW-Authenticate": "Bearer"})
    
    return None


@app.get("/api/noc/runs/{rid}")
def noc_read_synthetic_run(rid: str, authorization: str | None = Header(default=None)):
    """Bounded synthetic-only Run identity for portal NOC correlation."""
    denial = _noc_core_auth_failure(authorization)
    if denial is not None:
        return denial
    if not isinstance(rid, str) or _NOC_CORE_ID.fullmatch(rid) is None:
        return _noc_core_response({"detail": "noc_core_run_unavailable_or_unverified"}, 503)
    try:
        with db() as c:
            row = c.execute(
                "select r.run_id,r.incident_id,r.mode,r.status,i.synthetic,i.payload "
                "from aiops.runs r join aiops.incidents i "
                "on i.incident_id=r.incident_id where r.run_id=%s", (rid,)
            ).fetchone()
        if not row:
            raise ValueError("missing canonical Run or incident")
        run_id, incident_id, mode, status, synthetic, incident_payload = row
        if (not isinstance(run_id, str) or _NOC_CORE_ID.fullmatch(run_id) is None
                or not isinstance(incident_id, str)
                or _NOC_CORE_ID.fullmatch(incident_id) is None
                or mode not in ("DEMO", "REPLAY", "STORY")
                or not isinstance(status, str) or not status
                or synthetic is not True or not isinstance(incident_payload, dict)):
            raise ValueError("not a qualified synthetic Run")
        reject_unqualified_tenant_scope(incident_payload)
    except Exception:
        return _noc_core_response({"detail": "noc_core_run_unavailable_or_unverified"}, 503)
    return _noc_core_response({
        "run": {"run_id": run_id, "incident_id": incident_id,
                "mode": mode, "status": status},
        "data_classification": "SYNTHETIC_CANONICAL_RUN",
        "runtime_authenticated": False,
        "tenant_acl_qualified": False,
        "live_remediation_authorized": False,
    })


@app.get("/api/noc/runs/{rid}/policy-status")
def noc_read_demo_policy_status(rid: str, authorization: str | None = Header(default=None)):
    """Observe a DEMO Core Run and its stored Policy gate without any mutation.

    Internal bearer only; this is not a tenant-authorized portal endpoint.
    A missing gate is reported as MISSING, never inferred from Run status.
    """
    denial = _noc_core_auth_failure(authorization)
    if denial is not None:
        return denial
    if not isinstance(rid, str) or _NOC_CORE_ID.fullmatch(rid) is None:
        return _noc_core_response({"detail": "demo_policy_observation_unavailable"}, 503)
    try:
        with db() as c:
            row = c.execute(
                "select r.run_id,r.incident_id,r.mode,r.status,i.synthetic,i.payload,"
                "g.state,g.decision,r.created_at,g.evaluated_at,"
                "statement_timestamp() from aiops.runs r "
                "join aiops.incidents i on i.incident_id=r.incident_id "
                "left join aiops.gates g on g.run_id=r.run_id and g.stage='POLICY' "
                "where r.run_id=%s", (rid,)
            ).fetchone()
        observation = project_demo_policy_gate(row)
    except Exception:
        return _noc_core_response({"detail": "demo_policy_observation_unavailable"}, 503)
    return _noc_core_response(observation)
