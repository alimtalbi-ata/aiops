#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.986 | E2E CANDIDATE PARITY AND DEMO SAFETY ====='
IMAGE=aiops2-worker:fs001d-guard-validated-20261106
E2E=aiops2-e2e-v1-aiops2-worker-1
PROD=aiops2-rebuild-worker
docker image inspect "$IMAGE" >/dev/null
for name in "$E2E" "$PROD" aiops2-e2e-v1-aiops2-core-1 aiops2-e2e-v1-aiops2-temporal-1; do
 docker inspect "$name" --format 'CONTAINER={{.Name}} RUNNING={{.State.Running}} IMAGE={{.Config.Image}}'
done
echo '===== WORKER SOURCE PARITY ====='
docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib,pathlib; p=pathlib.Path("/app/worker/main.py"); print("GUARDED_IMAGE_SOURCE_SHA256="+hashlib.sha256(p.read_bytes()).hexdigest())'
docker exec "$E2E" python -c 'import hashlib,pathlib; p=pathlib.Path("/app/worker/main.py"); print("E2E_ACTIVE_SOURCE_SHA256="+hashlib.sha256(p.read_bytes()).hexdigest())'
echo '===== WORKFLOW CONTRACT ====='
python3 - <<'PY'
import ast,pathlib
p=pathlib.Path('/home/aiops/aiops2-fs-demo-source/app/worker/workflow.py')
s=p.read_text();t=ast.parse(s)
for n in t.body:
 if isinstance(n,ast.ClassDef) and n.name=='IncidentWorkflow':
  print(ast.get_source_segment(s,n))
PY
echo '===== E2E PORTAL PRESENCE AND DEMO GATE (NO SECRET VALUES) ====='
python3 - <<'PY'
import json,subprocess
for name in ['aiops2-e2e-v1-aiops2-portal-1','aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-worker-1']:
 try:
  x=json.loads(subprocess.check_output(['docker','inspect',name],stderr=subprocess.DEVNULL))[0]
 except subprocess.CalledProcessError:
  print('MISSING_CONTAINER='+name);continue
 env=dict(s.split('=',1) for s in x['Config'].get('Env',[]) if '=' in s)
 print('CONTAINER='+name+' RUNNING='+str(x['State']['Running']).lower())
 for k in ('AIOPS_DEMO_LAUNCH_ENABLED','CORE_URL','WORKER_URL','TEMPORAL_ADDRESS','EVIDENCE_URL','POLICY_URL','TWIN_URL','INTELLIGENCE_URL'):
  if k in env:print(' CONFIG_'+k+'='+env[k])
 print(' HAS_INTERNAL_TOKEN='+str(bool(env.get('AIOPS_INTERNAL_TOKEN') or env.get('AIOPS_ADMIN_TOKEN'))).lower())
PY
echo '===== SAFETY ====='
echo 'NO_HTTP_WRITES=YES'
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.986 ====='
