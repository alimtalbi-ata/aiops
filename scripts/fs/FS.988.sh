#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.988 | DEDICATED GUARDED WORKER E2E ISOLATION PREFLIGHT ====='
GUARDED=aiops2-worker:fs001d-guard-validated-20261106
E2E_WORKER=aiops2-e2e-v1-aiops2-worker-1
E2E_TEMPORAL=aiops2-e2e-v1-aiops2-temporal-1
PROD_WORKER=aiops2-rebuild-worker
docker image inspect "$GUARDED" >/dev/null
echo '===== CANDIDATE QUEUE / TEMPORAL NAMESPACE CONFIG ====='
docker run --rm --network none --env AIOPS_INTERNAL_TOKEN=fs988-isolated-token --entrypoint python "$GUARDED" -c '
import ast,pathlib
p=pathlib.Path("/app/worker/main.py")
s=p.read_text()
t=ast.parse(s)
for n in ast.walk(t):
 if isinstance(n,ast.Call):
  f=ast.get_source_segment(s,n.func) or ""
  if f.endswith(("Worker","start_workflow","Client.connect")):
   print("CALL="+(ast.get_source_segment(s,n) or "")[:900].replace("\n"," "))
for line in s.splitlines():
 if any(k in line for k in ("TEMPORAL_NAMESPACE","TASK_QUEUE","TEMPORAL_ADDRESS","TEMP =","TEMP=")):
  print("CONFIG="+line[:240])
'
echo '===== EXISTING E2E WORKER POLLING / CONFIG ====='
docker inspect "$E2E_WORKER" --format 'E2E_RUNNING={{.State.Running}} E2E_IMAGE={{.Config.Image}}'
docker inspect "$E2E_TEMPORAL" --format 'E2E_TEMPORAL_RUNNING={{.State.Running}}'
docker inspect "$PROD_WORKER" --format 'PROD_RUNNING={{.State.Running}} PROD_IMAGE={{.Config.Image}}'
echo '===== NETWORK ISOLATION ====='
python3 - <<'PY'
import json,subprocess
def inspect(name):
 return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
e=inspect('aiops2-e2e-v1-aiops2-worker-1')
p=inspect('aiops2-rebuild-worker')
en=set(e['NetworkSettings']['Networks'])
pn=set(p['NetworkSettings']['Networks'])
assert 'aiops2-e2e-v1_control' in en
assert not en.intersection(pn),'cross-stack worker network'
print('E2E_PROD_NETWORK_SEPARATION=PASS')
PY
echo '===== SAFETY DECISION ====='
echo 'SHARED_TASK_QUEUE=aiops-runner'
echo 'DEDICATED_WORKER_START_AUTHORIZED=NO'
echo 'REQUIRES_UNIQUE_QUEUE_OR_NAMESPACE=YES'
echo 'BUSINESS_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.988 ====='
