#!/usr/bin/env python3
"""Disposable, synthetic Core/Temporal demo using existing application code.

No Debian deployment, GLPI mutation, cron, or production Compose changes.
The compact application container is a storage-saving test fixture only.
"""
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
SERVICES = [('core', 810), ('worker', 815), ('twin', 811), ('policy', 813), ('evidence', 812), ('intelligence', 817)]
CLIENT = r'''
import asyncio,hashlib,json,os,sys,time,uuid,urllib.request,urllib.error
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Replayer
from worker.workflow import IncidentWorkflow
from shared.fresh_run_evidence import verify_run_evidence, verify_evidence_sql
import psycopg

def api(path, body=None):
    req=urllib.request.Request('http://127.0.0.1:810'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+os.environ['AIOPS_INTERNAL_TOKEN'],
                 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        route='HEALTH' if path=='/health' else ('INCIDENT_CREATE' if path=='/api/incidents' else ('RUN_CREATE' if path=='/api/runs' else ('RUN_EXECUTE' if path.endswith('/execute') else ('EVIDENCE_LIST' if path.endswith('/evidence') else 'RUN_DETAIL'))))
        raise RuntimeError('API_'+route+'_HTTP_'+str(exc.code)) from None

async def main():
    sources={str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in Path('/app').rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    manifest=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    if manifest!=sys.argv[1]:raise RuntimeError('IMAGE_SOURCE_MISMATCH')
    client=None
    for _ in range(60):
        try:
            api('/health')
            worker_req=urllib.request.Request('http://127.0.0.1:815/health')
            with urllib.request.urlopen(worker_req,timeout=5) as worker_response:
                if json.load(worker_response).get('status')!='ok':
                    raise RuntimeError('WORKER_NOT_READY')
            intel_req=urllib.request.Request('http://127.0.0.1:817/ready')
            with urllib.request.urlopen(intel_req,timeout=5) as intel_response:
                intel_health=json.load(intel_response)
            if not intel_health.get('provider_configured'):
                raise RuntimeError('INTELLIGENCE_MODEL_NOT_CONFIGURED')
            client=await Client.connect('temporal:7233')
            break
        except RuntimeError as exc:
            if str(exc)=='INTELLIGENCE_MODEL_NOT_CONFIGURED':raise
            await asyncio.sleep(1)
        except Exception:await asyncio.sleep(1)
    if client is None:
        raise RuntimeError('LOCAL_SERVICES_OR_INTELLIGENCE_NOT_READY')
    key='LOCAL-DEMO-'+uuid.uuid4().hex[:12].upper()
    incident=api('/api/incidents',{'external_id':key,'title':'Isolated synthetic demo',
        'severity':'P1','source':'local-qualification','synthetic':True})
    run=api('/api/runs',{'mode':'DEMO','scenario_id':'SCN-GOLDEN-PAYMENT-P1',
        'incident_id':incident['incident_id'],'idempotency_key':key})
    rid=run['run_id']
    api('/api/runs/'+rid+'/execute',{})
    for _ in range(90):
        detail=api('/api/runs/'+rid)
        if detail['run']['status'] in ('RESOLVED','BLOCKED','FAILED','CANCELLED'):break
        await asyncio.sleep(1)
    if detail['run']['status']!='RESOLVED':
        state=detail['run']['status']
        if state not in ('BLOCKED','FAILED','CANCELLED','WAITING','RUNNING','CREATED'):
            state='UNKNOWN'
        failed_stage=next((s.get('stage') for s in detail.get('stages',[])
                           if s.get('state') in ('BLOCKED','FAIL','FAILED')),None)
        if failed_stage not in ('NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG',
                               'DGX_ANALYST','DGX_CRITIC','POLICY','HITL','REMEDIATE',
                               'VERIFY','RECONCILE','LEARN'):failed_stage='UNKNOWN'
        raise RuntimeError('DEMO_NOT_RESOLVED_STATE_'+state+'_STAGE_'+failed_stage)
    if detail['run']['mode']!='DEMO':raise RuntimeError('NOT_SYNTHETIC_DEMO')
    required={'NORMALIZE','CORRELATE','CMDB','OBSERVE','RAG','DGX_ANALYST','DGX_CRITIC',
              'POLICY','HITL','REMEDIATE','VERIFY','RECONCILE','LEARN'}
    completed=[e for e in detail['events'] if e['event_type'] in ('STAGE_COMPLETED','ANALYST_COMPLETED','CRITIC_COMPLETED') and e['status']=='PASS']
    if not required <= {e['stage'] for e in completed}:raise RuntimeError('STAGES_INCOMPLETE')
    if not all(e.get('payload',{}).get('synthetic') is True for e in completed):raise RuntimeError('PROVENANCE_MISSING')
    if not any(g['stage']=='POLICY' and g['state']=='PASS' and g['decision']=='SIMULATE'
               for g in detail['gates']):raise RuntimeError('SIMULATE_GATE_MISSING')
    handle=client.get_workflow_handle(rid)
    description=await handle.describe()
    if description.status.name!='COMPLETED':raise RuntimeError('TEMPORAL_NOT_COMPLETED')
    history=await handle.fetch_history()
    await Replayer(workflows=[IncidentWorkflow]).replay_workflow(history)
    # A completed stage without a linked Evidence ID is not qualified.
    if any(not isinstance(e.get('evidence_ids'),list) or not e['evidence_ids']
           or any(not isinstance(i,str) or not i.strip() for i in e['evidence_ids'])
           for e in completed):
        raise RuntimeError('STAGE_EVIDENCE_LINK_MISSING')
    evidence={i for e in completed for i in e['evidence_ids']}
    listing=api('/api/runs/'+rid+'/evidence')
    def fetch_evidence(eid):
        req=urllib.request.Request('http://127.0.0.1:812/api/evidence/'+eid,
            headers={'Authorization':'Bearer '+os.environ['AIOPS_INTERNAL_TOKEN']})
        with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
    evidence_readback=verify_run_evidence(rid,completed,listing,fetch_evidence)
    with psycopg.connect(os.environ['DATABASE_URL']) as connection:
        sql_readback=verify_evidence_sql(rid,evidence,connection)
    evidence_readback.update(sql_readback)
    if len(evidence)<len(required):
        raise RuntimeError('EVIDENCE_COVERAGE_INCOMPLETE')
    print(json.dumps({'scope':'LOCAL_ISOLATED_SYNTHETIC_TEMPORAL','run_id':rid,
        'temporal_run_id':description.run_id,'application_manifest_sha256':manifest,'core_status':'RESOLVED',
        'temporal_status':'COMPLETED','completed_stages':len(required),
        'linked_synthetic_evidence':len(evidence),'evidence_readback':evidence_readback,'policy':'PASS/SIMULATE',
        'history_events':len(history.events),'replay':'PASS',
        'debian_verified':False,'glpi_verified':False,'portal_verified':False,
        'real_model_verified':False,'intelligence_provider':'SYNTHETIC_CI_FIXTURE' if os.environ.get('LLM_MODEL')=='synthetic-ci-fixture-v1' else 'REAL_MODEL_CONFIGURED_NOT_ATTESTED'}))
asyncio.run(main())
'''


def source_manifest(root):
    sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    return hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()


def port(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise argparse.ArgumentTypeError('port must be between 1024 and 65535')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker-host', default='unix:///var/run/docker.sock', help='local Docker Unix socket (rootless: unix:///run/user/UID/docker.sock)')
    parser.add_argument('--image', help='reuse an already built application image; otherwise build source')
    parser.add_argument('--synthetic-fixture', action='store_true', help='isolated DEMO-only deterministic model fixture; never a real model')
    parser.add_argument('--keep', action='store_true', help='leave this isolated demo and Temporal UI running')
    parser.add_argument('--ui-port', type=port, default=18233)
    parser.add_argument('--core-port', type=port, default=18100)
    args = parser.parse_args()
    if not args.docker_host.startswith('unix:///'):
        parser.error('only a local Docker Unix socket is accepted')
    if args.ui_port == args.core_port:
        parser.error('Core and UI require different ports')
    model_inputs = tuple(bool(os.environ.get(key, '').strip())
                         for key in ('LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY'))
    if not args.synthetic_fixture and not all(model_inputs):
        print('LOCAL_DEMO=BLOCKED: INTELLIGENCE_MODEL_NOT_CONFIGURED; '
              'set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY; no containers started.',
              file=sys.stderr)
        return 2
    if not args.synthetic_fixture and not os.environ['LLM_BASE_URL'].strip().startswith('https://'):
        print('LOCAL_DEMO=BLOCKED: LLM_BASE_URL_REQUIRES_HTTPS; '
              'no containers started.', file=sys.stderr)
        return 2
    required_gib = 1 if args.image else 2
    if shutil.disk_usage(tempfile.gettempdir()).free < required_gib * 1024**3:
        print(f'LOCAL_DEMO=BLOCKED: at least {required_gib} GiB free disk required; nothing started.', file=sys.stderr)
        return 2
    folder = Path(tempfile.mkdtemp(prefix='aiops-local-demo-'))
    project = 'aiops-local-demo-' + secrets.token_hex(4)
    environment = os.environ.copy()
    for name in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        environment.pop(name, None)
    docker = ['docker', '--host=' + args.docker_host]

    def call(command, **kwargs):
        return subprocess.run(command, env=environment, check=True, timeout=600, **kwargs)

    config = folder / 'compose.json'
    compose = docker + ['compose', '-f', str(config)]
    started = False
    success = False
    try:
        call(docker + ['info', '--format', '{{.ServerVersion}}'])
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
        image = args.image or 'aiops-local-demo:' + revision[:12]
        if args.image is None:
            dockerfile = folder / 'Dockerfile'
            dockerfile.write_text('''# syntax=docker/dockerfile:1
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=proxy_ca if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONPATH=/app
''')
            build = docker + ['build', '-f', str(dockerfile), '-t', image,
                              '--label', 'org.opencontainers.image.revision=' + revision]
            if environment.get('CODEX_PROXY_CERT'):
                build += ['--secret', 'id=proxy_ca,src=' + environment['CODEX_PROXY_CERT']]
            call(build + [str(REPO / 'app')])
        password, token = secrets.token_hex(24), secrets.token_hex(32)
        no_proxy = environment.get('NO_PROXY', '') + ',127.0.0.1,localhost,0.0.0.0,pg,temporal'
        env = {'AIOPS_INTERNAL_TOKEN': token, 'AIOPS_ADMIN_TOKEN': token, 'ADMIN_TOKEN': token,
               'DATABASE_URL': f'postgresql://aiops:{password}@pg:5432/aiops',
               'TEMPORAL_ADDRESS': 'temporal:7233', 'NO_PROXY': no_proxy, 'no_proxy': no_proxy}
        # Opt-in real model credentials; never substitute synthetic Analyst/Critic output.
        # The disposable Compose file is mode 0600 and removed on teardown.
        model_base = environment.get('LLM_BASE_URL', '').strip()
        model_name = environment.get('LLM_MODEL', '').strip()
        model_key = environment.get('LLM_API_KEY', '').strip()
        if args.synthetic_fixture:
            env.update({'LLM_BASE_URL':'http://127.0.0.1:818',
                        'LLM_MODEL':'synthetic-ci-fixture-v1',
                        'LLM_API_KEY':'synthetic-ci-only-no-credential'})
        elif model_base and model_name and model_key:
            if not model_base.startswith('https://'):
                raise RuntimeError('LLM_BASE_URL_REQUIRES_HTTPS')
            env.update({'LLM_BASE_URL': model_base, 'LLM_MODEL': model_name,
                        'LLM_API_KEY': model_key})
        for name, service_port in SERVICES:
            if name != 'worker':
                env[name.upper() + '_URL'] = f'http://127.0.0.1:{service_port}'
        env['WORKER_URL'] = 'http://127.0.0.1:815'
        service_processes = SERVICES + ([('qualification_fixture', 818)] if args.synthetic_fixture else [])
        supervisor = ('import subprocess,time; processes=[subprocess.Popen(["uvicorn",name+".main:app",'
                      '"--host","0.0.0.0","--port",str(port)]) for name,port in ' + repr(service_processes) + '];\n'
                      'while all(p.poll() is None for p in processes): time.sleep(1)\nraise SystemExit(1)')
        data = {'name': project, 'networks': {'default': {}}, 'services': {
            'pg': {'image': 'postgres:16-alpine', 'tmpfs': ['/var/lib/postgresql/data'],
                   'environment': {'POSTGRES_DB': 'aiops', 'POSTGRES_USER': 'aiops', 'POSTGRES_PASSWORD': password},
                   'healthcheck': {'test': ['CMD', 'pg_isready', '-U', 'aiops'], 'interval': '2s', 'retries': 30}},
            'temporal': {'image': 'temporalio/temporal:1.10.0',
                         'command': ['server', 'start-dev', '--ip', '0.0.0.0', '--ui-ip', '0.0.0.0', '--db-filename', '/tmp/temporal.db'],
                         'environment': {'NO_PROXY': no_proxy, 'no_proxy': no_proxy},
                         'ports': [f'127.0.0.1:{args.ui_port}:8233']},
            'apps': {'image': image, 'environment': env, 'command': ['python', '-c', supervisor],
                     'ports': [f'127.0.0.1:{args.core_port}:810'],
                     'depends_on': {'pg': {'condition': 'service_healthy'}}}}}
        config.write_text(json.dumps(data, indent=2))
        config.chmod(0o600)
        started = True
        call(compose + ['create', 'pg'])
        migration_dir = folder / 'migrations'
        migration_dir.mkdir(mode=0o755)
        for source in (REPO / 'db/migrations').glob('*.sql'):
            target = migration_dir / source.name
            target.write_bytes(source.read_bytes())
            target.chmod(0o644)
        pg = call(compose + ['ps', '-a', '-q', 'pg'], capture_output=True, text=True).stdout.strip()
        call(docker + ['cp', str(migration_dir) + '/.', pg + ':/docker-entrypoint-initdb.d/'])
        call(compose + ['up', '-d'])
        run = call(compose + ['exec', '-T', 'apps', 'python', '-', source_manifest(REPO / 'app')], input=CLIENT, text=True, capture_output=True)
        receipt = json.loads(run.stdout)
        receipt['runner_commit'] = revision
        receipt['image_id'] = call(docker + ['image', 'inspect', image, '--format', '{{.Id}}'],
                                   capture_output=True, text=True).stdout.strip()
        receipt['temporal_ui'] = f'http://127.0.0.1:{args.ui_port}/namespaces/default/workflows/{receipt["run_id"]}/{receipt["temporal_run_id"]}/history'
        receipt['cleanup_command'] = 'docker --host=' + args.docker_host + ' compose -f ' + str(config) + ' down'
        output = folder / 'receipt.json'
        output.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
        print('Receipt:', output)
        success = True
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Never publish command arguments, subprocess output, tokens or raw API bodies.
        # Only emit explicitly allowlisted machine error markers from the child.
        child_output = (error.stderr or '') if isinstance(error, subprocess.CalledProcessError) else ''
        allowed = ('IMAGE_SOURCE_MISMATCH', 'LOCAL_SERVICES_NOT_READY', 'DEMO_NOT_RESOLVED',
                   'STAGES_INCOMPLETE', 'PROVENANCE_MISSING', 'SIMULATE_GATE_MISSING',
                   'STAGE_EVIDENCE_LINK_MISSING', 'EVIDENCE_COVERAGE_INCOMPLETE',
                   'CORE_EVIDENCE_READBACK_INCOMPLETE', 'EVIDENCE_DIGEST_MISMATCH',
                   'SQL_EVIDENCE_ROWS_MISSING', 'SQL_RUN_EVENT_LINK_MISMATCH',
                   'SQL_EVIDENCE_DIGEST_INVALID', 'TEMPORAL_NOT_COMPLETED')
        marker = next((code for code in allowed if code in child_output), 'UNCLASSIFIED_CHILD_FAILURE')
        if 'INTELLIGENCE_MODEL_NOT_CONFIGURED' in child_output:
            marker = 'INTELLIGENCE_MODEL_NOT_CONFIGURED'
        demo_failure = re.search(r'DEMO_NOT_RESOLVED_STATE_(?:BLOCKED|FAILED|CANCELLED|WAITING|RUNNING|CREATED|UNKNOWN)_STAGE_(?:NORMALIZE|CORRELATE|CMDB|OBSERVE|RAG|DGX_ANALYST|DGX_CRITIC|POLICY|HITL|REMEDIATE|VERIFY|RECONCILE|LEARN|UNKNOWN)', child_output)
        if demo_failure: marker = demo_failure.group(0)
        api_failure = re.search(r'API_(?:HEALTH|INCIDENT_CREATE|RUN_CREATE|RUN_EXECUTE|RUN_DETAIL|EVIDENCE_LIST)_HTTP_(?:400|401|403|404|409|422|429|500|502|503|504)', child_output)
        if api_failure: marker = api_failure.group(0)
        categories = ('ModuleNotFoundError', 'ImportError', 'OperationalError', 'ConnectionRefusedError',
                      'HTTPError', 'RuntimeError', 'KeyError', 'TypeError', 'ValueError',
                      'WorkflowFailureError', 'TimeoutError', 'IntegrityError')
        category = next((name for name in categories if name + ':' in child_output), 'UNCLASSIFIED')
        print('LOCAL_DEMO=FAILED: ' + type(error).__name__ + ' marker=' + marker +
              ' category=' + category + '; no success receipt produced.', file=sys.stderr)
        return 1
    finally:
        if started and (not args.keep or not success):
            subprocess.run(compose + ['down', '--remove-orphans'], env=environment, timeout=90, check=False)


if __name__ == '__main__':
    raise SystemExit(main())
