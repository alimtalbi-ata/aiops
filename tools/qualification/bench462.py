#!/usr/bin/env python3
"""Qualify the actual #194 candidate services on an exclusively local disposable bench.

Reuses source-manifest/resource guards from #468's run_local_temporal_demo.py.
Does not deploy, contact GLPI, expose ports, or convert a DEMO into a LIVE proof.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile
import time

REPO = Path(__file__).resolve().parents[2]
BASE = '40d38705cf2bde3be6052340442c117a81908f65'
TEMPORAL_IMAGE = 'temporalio/temporal:1.4.1@sha256:9844298258519ebece82b3253f1ee1fc4eb8d87b7abcc264cfb676be342c74a5'
SERVICES = {'core':810, 'worker':815, 'twin':811, 'policy':813, 'evidence':812, 'intelligence':817}
CLIENT = r'''
import asyncio,hashlib,json,os,sys,time,urllib.request,urllib.error,uuid
from pathlib import Path
import psycopg
from temporalio.client import Client
from temporalio.worker import Replayer
from worker.workflow import IncidentWorkflow

def api(path, body=None):
    req=urllib.request.Request('http://core:810'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+os.environ['AIOPS_INTERNAL_TOKEN'], 'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)

def sql(query,values=()):
    with psycopg.connect(os.environ['DATABASE_URL']) as c:
        return c.execute(query,values).fetchone()

async def main():
    client=await Client.connect('temporal:7233')
    if sys.argv[1]=='retry':
        rid=sys.argv[2]
        h=client.get_workflow_handle(rid)
        before=await h.describe();history=await h.fetch_history()
        n=len(history.events)
        attempts=[api('/api/runs/'+rid+'/execute',{}) for _ in range(3)]
        assert all(r.get('idempotent') is True and r.get('workflow_id')==rid and r.get('run_id')==rid for r in attempts), 'RETRY_RECEIPT_MISMATCH'
        after=await h.describe();latest=await h.fetch_history()
        assert after.run_id==before.run_id and len(latest.events)==n, 'RETRY_CREATED_TEMPORAL_EVENTS'
        assert sql('select count(*) from aiops.execution_receipts where run_id=%s',(rid,))[0]==1
        print(json.dumps({'run_id':rid,'retry_count':3,'idempotent':True,'same_temporal_run_id':after.run_id,'history_events_before':n,'history_events_after':len(latest.events),'execution_receipt_rows':1}))
        return
    manifest={str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in Path('/app').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    assert digest==sys.argv[2], 'IMAGE_SOURCE_MISMATCH'
    key='BENCH462-'+uuid.uuid4().hex[:12].upper()
    incident=api('/api/incidents',{'external_id':key,'title':'Isolated #194 DEMO qualification', 'severity':'P1','source':'isolated-bench462','synthetic':True})
    run=api('/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1','incident_id':incident['incident_id'],'idempotency_key':key})
    rid=run['run_id'];first=api('/api/runs/'+rid+'/execute',{})
    assert first['run_id']==rid and first['workflow_id']==rid
    for _ in range(150):
        detail=api('/api/runs/'+rid)
        if detail['run']['status'] in ('RESOLVED','BLOCKED','FAILED','CANCELLED'):break
        await asyncio.sleep(1)
    Path('/tmp/bench462-run.json').write_text(json.dumps(detail,default=str))
    ledger=api('/api/runs/'+rid+'/ai-ledger')
    Path('/tmp/bench462-ledger.json').write_text(json.dumps(ledger,default=str))
    assert detail['run']['status']=='RESOLVED', 'DEMO_NOT_RESOLVED:'+detail['run']['status']
    assert detail['run']['mode']=='DEMO'
    stages={x['stage']:x['state'] for x in detail['stages']}
    required={'NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG','DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN'}
    assert all(stages.get(s)=='PASS' for s in required), 'STAGES_INCOMPLETE'
    assert ledger.get('analyses') and ledger.get('critiques') and ledger.get('policy_decisions'), 'NATIVE_LEDGER_MISSING'
    assert any(q.get('validated') is True for q in ledger['critiques']), 'CRITIC_NOT_VALIDATED'
    assert any(g['stage']=='POLICY' and g['state']=='PASS' and g['decision']=='SIMULATE' for g in detail['gates']), 'SIMULATE_GATE_MISSING'
    hitl=next(e for e in detail['events'] if e['event_type']=='HITL_SIMULATION_SKIPPED')
    assert hitl['payload'].get('execution_allowed') is False and hitl['payload'].get('synthetic') is True
    assert sql('select count(*) from aiops.approval_records')[0]==0, 'DEMO_MINTED_APPROVAL'
    assert sql('select count(*) from aiops.hitl_decision_outbox')[0]==0, 'DEMO_MINTED_APPROVAL_OUTBOX'
    outbox=api('/api/hitl/decision-outbox/status')
    # A server-owned token is not an OIDC human assertion.
    try:api('/api/proposals/nonexistent/approval',{'decision':'APPROVE'})
    except urllib.error.HTTPError as exc:
        assert exc.code in (401,403,503), 'UNEXPECTED_OIDC_REJECTION'
        oidc_rejection=exc.code
    else:raise AssertionError('INTERNAL_TOKEN_AUTHORIZED_HUMAN_APPROVAL')
    handle=client.get_workflow_handle(rid);description=await handle.describe()
    assert description.status.name=='COMPLETED', 'TEMPORAL_NOT_COMPLETED'
    history=await handle.fetch_history()
    Path('/tmp/bench462-history.json').write_text(history.to_json())
    await Replayer(workflows=[IncidentWorkflow]).replay_workflow(history)
    assert sql('select count(*) from aiops.execution_receipts where run_id=%s',(rid,))[0]==1
    print(json.dumps({'scope':'CLOUD_ISOLATED_DEMO_194_NATIVE_SERVICES','run_id':rid,'incident_id':incident['incident_id'],'temporal_run_id':description.run_id,
        'application_manifest_sha256':digest,'core_status':'RESOLVED','temporal_status':'COMPLETED','stages':stages,
        'history_events':len(history.events),'sdk_replay':'PASS','execution_receipt_rows':1,
        'analysis_records':len(ledger['analyses']),'critique_records':len(ledger['critiques']),'policy_records':len(ledger['policy_decisions']),
        'policy':'PASS/SIMULATE','hitl':'DEMO_SYNTHETIC_NO_EXECUTION_AUTHORITY','native_approval_rows':0,'hitl_outbox_rows':0,
        'oidc_internal_token_rejected_http':oidc_rejection,'outbox_read_status':outbox,
        'provider':'EXISTING_DETERMINISTIC_SYNTHETIC_TEST_PROVIDER','real_model_verified':False,'real_oidc_approval_verified':False,
        'debian_verified':False,'glpi_verified':False,'browser_verified':False,'real_fs1250_e2e':'HOLD'}))
asyncio.run(main())
'''


def source_manifest(root):
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    return files,hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('/workspace/aiops-bench-462'))
    args=parser.parse_args()
    if shutil.disk_usage(args.root.parent).free < 4*1024**3:
        raise SystemExit('BENCH_BLOCKED: at least 4 GiB free required; nothing started')
    if subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True).strip():
        raise SystemExit('BENCH_BLOCKED: commit source changes before qualification')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    subprocess.run(['git','merge-base','--is-ancestor',BASE,revision],cwd=REPO,check=True)
    project='aiops2-agent7-462-'+secrets.token_hex(4)
    folder=args.root/project;folder.mkdir(parents=True,mode=0o700)
    environment=os.environ.copy()
    for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):
        environment.pop(key,None)
    docker=['docker','--host=unix:///var/run/docker.sock']
    def call(command,**kwargs):
        return subprocess.run(command,env=environment,check=True,timeout=kwargs.pop('timeout',900),**kwargs)
    call(docker+['info','--format','{{.ServerVersion}}'])
    source=folder/'source';source.mkdir()
    data=subprocess.check_output(['git','archive',revision,'--','app','db/migrations'],cwd=REPO)
    tarfile.open(fileobj=io.BytesIO(data)).extractall(source,filter='data')
    files,digest=source_manifest(source/'app')
    image='aiops2-agent7-462:'+digest[:16]
    config=folder/'compose.json';artifacts=folder/'artifacts';artifacts.mkdir()
    (artifacts/'source-manifest.json').write_text(json.dumps({'source_commit':revision,'base_commit':BASE,'application_sha256':digest,'files':files},indent=2)+'\n')
    print('BENCH_PROJECT='+project+'\nBENCH_FOLDER='+str(folder),flush=True)
    exists=subprocess.run(docker+['image','inspect',image],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not exists:
        call(docker+['build','--progress=plain','--secret','id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt',
             '-f',str(Path(__file__).with_suffix('.Dockerfile')),'-t',image,
             '--label','org.opencontainers.image.revision='+revision,'--label','aiops2.source_manifest='+digest,str(source/'app')])
    image_data=json.loads(call(docker+['image','inspect',image],capture_output=True,text=True).stdout)[0]
    assert image_data['Config']['Labels']['aiops2.source_manifest']==digest
    token,password=secrets.token_hex(32),secrets.token_hex(24)
    no_proxy=environment.get('NO_PROXY','')+',localhost,127.0.0.1,0.0.0.0,postgres,temporal,provider,'+','.join(SERVICES)
    common={'AIOPS_INTERNAL_TOKEN':token,'AIOPS_ADMIN_TOKEN':token,'ADMIN_TOKEN':token,
            'DATABASE_URL':f'postgresql://aiops:{password}@postgres:5432/aiops','TEMPORAL_ADDRESS':'temporal:7233',
            'NO_PROXY':no_proxy,'no_proxy':no_proxy,'AIOPS_HITL_IDENTITY_MODE':'DISABLED','AIOPS_HITL_SIMULATOR_ENABLED':'false'}
    common.update({name.upper()+'_URL':f'http://{name}:{port}' for name,port in SERVICES.items() if name!='intelligence'})
    common['INTELLIGENCE_URL']='http://intelligence:817'
    service={'postgres':{'image':'postgres:16-alpine','tmpfs':['/var/lib/postgresql/data'],
            'environment':{'POSTGRES_DB':'aiops','POSTGRES_USER':'aiops','POSTGRES_PASSWORD':password},
            'healthcheck':{'test':['CMD','pg_isready','-U','aiops'],'interval':'2s','retries':40}},
        'temporal':{'image':TEMPORAL_IMAGE,'command':['server','start-dev','--ip','0.0.0.0','--headless','--db-filename','/tmp/temporal.db'],
                    'environment':{'NO_PROXY':no_proxy,'no_proxy':no_proxy}},
        'provider':{'image':image,'command':['python','/app/test_provider/main.py'],'environment':{'NO_PROXY':no_proxy,'no_proxy':no_proxy}}}
    for name,port in SERVICES.items():
        env=dict(common)
        if name=='intelligence':env.update(LLM_BASE_URL='http://provider:818/v1',LLM_MODEL='existing-deterministic-synthetic-fixture',LLM_TIMEOUT_SECONDS='20')
        if name=='policy':env['AIOPS_POLICY_STATE_DB']='/state/autonomy.sqlite3'
        service[name]={'image':image,'command':['uvicorn',name+'.main:app','--host','0.0.0.0','--port',str(port)],
          'environment':env,'depends_on':{'postgres':{'condition':'service_healthy'}},
          'healthcheck':{'test':['CMD','python','-c',f'import urllib.request;urllib.request.urlopen("http://127.0.0.1:{port}/health",timeout=2)'],'interval':'3s','retries':40},
          'tmpfs':['/state'] if name=='policy' else []}
    for spec in service.values():spec['labels']={'aiops2.bench.owner':'agent7','aiops2.bench.project':project}
    config.write_text(json.dumps({'name':project,'services':service,'networks':{'default':{'internal':True}}},indent=2));config.chmod(0o600)
    compose=docker+['compose','-p',project,'-f',str(config)]
    def safe_output(value):
        return value.replace(token,'[REDACTED]').replace(password,'[REDACTED]')
    def capture_logs():
        r=subprocess.run(compose+['logs','--no-color'],env=environment,capture_output=True,text=True,timeout=30)
        (artifacts/'services.log').write_text(safe_output(r.stdout+r.stderr))
    def client(mode,*extra):
        p=subprocess.run(compose+['exec','-T','core','python','-',mode,*extra],env=environment,input=CLIENT,text=True,capture_output=True,timeout=240)
        (artifacts/('client-'+mode+'.log')).write_text(safe_output(p.stdout+p.stderr))
        if p.returncode:raise RuntimeError('CLIENT_'+mode+'_FAILED: see redacted artifact log')
        return json.loads(p.stdout)
    def dispatches():
        p=call(compose+['logs','--no-color','worker'],capture_output=True,text=True)
        return p.stdout.count('"POST /api/execution/start HTTP/1.1"')
    try:
        call(compose+['create','postgres'])
        pg=call(compose+['ps','-a','-q','postgres'],capture_output=True,text=True).stdout.strip()
        call(docker+['cp',str(source/'db/migrations')+'/.',pg+':/docker-entrypoint-initdb.d/'])
        call(compose+['up','-d'])
        ready=False
        for attempt in range(60):
            probe=call(compose+['ps','--format','json'],capture_output=True,text=True)
            states=[json.loads(line) for line in probe.stdout.splitlines() if line.startswith('{')]
            healthy={s.get('Service') for s in states if s.get('Health')=='healthy'}
            running={s.get('Service') for s in states if s.get('State')=='running'}
            if set(SERVICES)<=healthy and {'provider','temporal'}<=running:ready=True;break
            if attempt%10==0:print('READINESS healthy='+','.join(sorted(healthy)),flush=True)
            time.sleep(1)
        if not ready:raise RuntimeError('SERVICES_NOT_READY')
        print('SERVICES_READY',flush=True)
        # The previous dev image crashed its background scanner after ~60 s.
        # Validate services beyond that interval rather than accepting a short run.
        initial_ids={}
        for name in ('temporal', 'core', 'worker'):
            initial_ids[name]=call(compose+['ps','-q',name],capture_output=True,text=True).stdout.strip()
        stability_started=time.monotonic()
        while time.monotonic()-stability_started < 90:
            for name,cid in initial_ids.items():
                snapshot=json.loads(call(docker+['inspect',cid],capture_output=True,text=True).stdout)[0]
                assert snapshot['State']['Status']=='running' and snapshot['RestartCount']==0, 'STABILITY_FAILURE_'+name
            if int(time.monotonic()-stability_started)%15==0:
                print('STABILITY_CHECK seconds='+str(int(time.monotonic()-stability_started)),flush=True)
            time.sleep(3)
        first=client('run',digest)
        before=dispatches();assert before==1, 'FIRST_DISPATCH_COUNT_NOT_ONE'
        retry=client('retry',first['run_id']);after=dispatches()
        assert after==before, 'SECOND_WORKER_DISPATCH'
        first.update(stability_observed_seconds=int(time.monotonic()-stability_started),temporal_dev_image=TEMPORAL_IMAGE,retry=retry,worker_dispatches_before_retry=before,worker_dispatches_after_retry=after,
                     source_commit=revision,source_base=BASE,image_id=image_data['Id'],image_source_revision=image_data['Config']['Labels'].get('org.opencontainers.image.revision'),
                     project=project,bench_result='PASS_ISOLATED_DEMO_ONLY',real_e2e='HOLD')
        (artifacts/'receipt.json').write_text(json.dumps(first,indent=2)+'\n')
        core=call(compose+['ps','-q','core'],capture_output=True,text=True).stdout.strip()
        for name in ['run','ledger','history']:
            call(docker+['cp',core+':/tmp/bench462-'+name+'.json',str(artifacts/(name+'.json'))])
        capture_logs()
        print(json.dumps(first,indent=2),flush=True)
        print('BENCH_RECEIPT='+str(artifacts/'receipt.json'),flush=True)
        return 0
    except Exception as exc:
        capture_logs()
        (artifacts/'failure.json').write_text(json.dumps({'error':type(exc).__name__,'reason':safe_output(str(exc)),'source_commit':revision,'real_e2e':'HOLD','scope':'OWNED_CLOUD_BENCH_ONLY'},indent=2)+'\n')
        print('BENCH_FAILED: '+safe_output(str(exc))+'; resources retained under '+str(folder),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
