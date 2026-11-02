#!/usr/bin/env python3
"""Strict Debian ACME sandbox E2E: no LIVE effects, no real GLPI writes.

Only POST after five independent service sandbox capability checks. A missing
capability is BLOCKED and never substituted with a fake human approval.
Secrets remain inside the simulator container, never in host argv/receipts.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

STATE = Path('/home/aiops/.local/state/aiops-debian-agent')
RECEIPT = STATE / 'acme-sim-e2e.json'
TENANT = 'ACME-TEST'
SCENARIO = 'ACME-SAN-PAYMENTS'
SERVICES = {
    'simulator': ('aiops2-rebuild-simulator', 816),
    'core': ('aiops2-rebuild-core', 810),
    'twin': ('aiops2-rebuild-twin', 811),
    'policy': ('aiops2-rebuild-policy', 813),
    'worker': ('aiops2-rebuild-worker', 815),
}
CAPABILITY_PATH = '/api/sandbox/acme/capabilities'
PY_IN_CONTAINER = """import json,os,sys,urllib.request,urllib.error
port,path,method,body,auth=sys.argv[1:]
headers={'Accept':'application/json','Content-Type':'application/json'}
if auth=='1':
 token=os.environ.get('AIOPS_INTERNAL_TOKEN','')
 if not token: print(json.dumps({'error':'INTERNAL_AUTH_UNAVAILABLE'})); sys.exit(2)
 headers['Authorization']='Bearer '+token
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None
req=urllib.request.Request('http://127.0.0.1:'+port+path,
 data=body.encode('utf-8') if method=='POST' else None,method=method,headers=headers)
try:
 with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=5) as r:
  data=r.read(32769)
  if len(data)>32768: raise ValueError('oversize')
  print(json.dumps({'http_status':r.status,'body':json.loads(data)}))
except urllib.error.HTTPError as e:
 print(json.dumps({'http_status':e.code,'error':'HTTP_DENIED'})); sys.exit(2)
except Exception as e:
 print(json.dumps({'error':'PROBE_FAILED_'+type(e).__name__})); sys.exit(2)
"""

def probe(component, path, method='GET', payload=None, auth=False, runner=subprocess.run):
    if component not in SERVICES or not path.startswith('/api/sandbox/acme/'):
        raise ValueError('non_sandbox_endpoint_refused')
    if method not in ('GET', 'POST'):
        raise ValueError('unsupported_method')
    container, port = SERVICES[component]
    body = json.dumps(payload, sort_keys=True, separators=(',', ':')) if payload is not None else ''
    cmd = ['docker', 'exec', container, 'python3', '-c', PY_IN_CONTAINER,
           str(port), path, method, body, '1' if auth else '0']
    try:
        p = runner(cmd, capture_output=True, text=True, timeout=12, check=False)
        if p.returncode or len(p.stdout) > 32768:
            return {'error': 'CONTAINER_PROBE_FAILED', 'component': component}
        out = json.loads(p.stdout)
        if not isinstance(out, dict) or out.get('http_status') != 200 or not isinstance(out.get('body'), dict):
            return {'error': 'CAPABILITY_OR_READBACK_UNAVAILABLE', 'component': component,
                    'http_status': out.get('http_status')}
        return out['body']
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {'error': 'CONTAINER_PROBE_UNAVAILABLE', 'component': component}

def qualified_capability(component, data):
    return (isinstance(data, dict) and data.get('schema') == 'aiops.acme-sandbox-capabilities.v1'
            and data.get('component') == component and data.get('tenant_id') == TENANT
            and data.get('mode') == 'SIMULATION' and data.get('isolated') is True
            and data.get('live_effects_allowed') is False
            and data.get('real_glpi_writes_allowed') is False
            and data.get('human_approval_claimed') is False
            and data.get('approval_issuer') == 'TWIN_ACME_SIMULATED')

def receipt(attempt_id, status, reason, stages=None, ids=None):
    return {
        'schema': 'aiops.debian-acme-sim-e2e.v1',
        'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'attempt_id': attempt_id, 'tenant_id': TENANT, 'scenario_id': SCENARIO,
        'mode': 'SIMULATION', 'approval_issuer': 'TWIN_ACME_SIMULATED',
        'human_approval_claimed': False, 'live_effects_allowed': False,
        'real_glpi_writes_allowed': False, 'status': status, 'reason': reason,
        'stages': stages or {}, 'ids': ids or {}, 'docker_mutations': 0,
    }

def validate_final(attempt_id, ids, reads):
    if not all(isinstance(x, dict) for x in reads.values()):
        return False
    core, twin, policy, worker = (reads[k] for k in ('core', 'twin', 'policy', 'worker'))
    for x in reads.values():
        if x.get('attempt_id') != attempt_id or x.get('tenant_id') != TENANT:
            return False
        if x.get('incident_id') != ids['incident_id'] or x.get('run_id') != ids['run_id']:
            return False
    return (core.get('incident_status') == 'RESOLVED' and core.get('run_status') == 'RESOLVED'
            and core.get('ticket_id') == ids['ticket_id']
            and core.get('ticket_authority') == 'SIMULATED_ONLY'
            and core.get('ticket_status') == 'RESOLVED'
            and core.get('source') == 'SYNTHETIC_SIMULATOR'
            and core.get('analysis_validated') is True
            and core.get('critic_validated') is True
            and type(core.get('evidence_count')) is int and core['evidence_count'] >= 2
            and twin.get('impact_root') == 'ACME-SAN-FABRIC-A'
            and twin.get('approval_id') == ids['approval_id']
            and twin.get('approval_issuer') == 'TWIN_ACME_SIMULATED'
            and twin.get('approval_kind') == 'SIMULATED'
            and twin.get('approval_actor') == 'TWIN_ACME_SIMULATED'
            and 'ACME-SVC-PAYMENTS' in twin.get('impacted_cis', [])
            and policy.get('decision') == 'SIMULATE'
            and policy.get('approval_kind') == 'SIMULATED'
            and policy.get('human_approved') is False
            and policy.get('live_effects_allowed') is False
            and worker.get('action') == 'SIMULATE'
            and worker.get('receipt_status') == 'SIMULATED_NO_EFFECT'
            and worker.get('effect_receipts') == 0
            and worker.get('execution_allowed') is False)

def execute(prober=probe, attempt_id=None):
    attempt_id = attempt_id or 'ACME-SIM-' + uuid.uuid4().hex[:16].upper()
    stages = {}
    for component in SERVICES:
        data = prober(component, CAPABILITY_PATH)
        ok = qualified_capability(component, data)
        stages['capability_' + component] = 'PASS' if ok else 'BLOCKED'
        if not ok:
            return receipt(attempt_id, 'BLOCKED', 'SANDBOX_CAPABILITY_MISSING_' + component.upper(), stages)
    request = {'attempt_id': attempt_id, 'tenant_id': TENANT,
               'scenario_id': SCENARIO, 'mode': 'SIMULATION',
               'approval_issuer': 'TWIN_ACME_SIMULATED',
               'idempotency_key': attempt_id, 'live_effects_allowed': False}
    started = prober('simulator', '/api/sandbox/acme/e2e', 'POST', request, True)
    keys = ('incident_id', 'run_id', 'ticket_id', 'proposal_id', 'approval_id')
    ids = {k: started.get(k) for k in keys} if isinstance(started, dict) else {}
    if (started.get('attempt_id') != attempt_id or started.get('tenant_id') != TENANT
            or any(not isinstance(ids.get(k), str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,100}', ids[k]) for k in keys)
            or started.get('glpi_mode') != 'SIMULATED_ONLY'):
        return receipt(attempt_id, 'FAIL', 'SIMULATOR_START_UNQUALIFIED', stages)
    stages['simulator_start'] = 'PASS'
    reads = {}
    for iteration in range(30):
        for component in ('core', 'twin', 'policy', 'worker'):
            reads[component] = prober(component, '/api/sandbox/acme/e2e/' + attempt_id, 'GET', None, True)
            stages['readback_' + component] = 'PASS' if isinstance(reads[component], dict) and not reads[component].get('error') else 'FAIL'
        if validate_final(attempt_id, ids, reads):
            break
        if iteration < 29:
            time.sleep(2)
    if not validate_final(attempt_id, ids, reads):
        return receipt(attempt_id, 'FAIL', 'INDEPENDENT_READBACK_OR_RESOLUTION_MISMATCH', stages, ids)
    stages['resolved'] = 'PASS'
    return receipt(attempt_id, 'PASS', 'SIMULATED_SANDBOX_ONLY', stages, ids)

def save(report, path=RECEIPT):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.acme-sim-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(report, f, sort_keys=True, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    report = execute()
    save(report)
    print('ACME_SIM_E2E=' + report['status'] + ' reason=' + report['reason'])
    return 0 if report['status'] in ('PASS', 'BLOCKED') else 78

if __name__ == '__main__':
    sys.exit(main())
