#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.984 | INCIDENT WORKFLOW EXECUTION READINESS ====='
ROOT=/home/aiops/aiops2-fs-demo-source
SRC="$ROOT/integration/worker-fs-candidate/main.py"
echo "7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b  $SRC" | sha256sum -c -
echo '===== TEMPORAL WORKFLOW DEFINITIONS ====='
python3 - "$SRC" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
for n in ast.walk(t):
 if isinstance(n,(ast.ClassDef,ast.AsyncFunctionDef,ast.FunctionDef)):
  decorators=[ast.get_source_segment(s,d) or '' for d in getattr(n,'decorator_list',[])]
  if any('workflow.' in d for d in decorators) or n.name in ('_execute_stage_blocking','startup','start_acme_simulated'):
   print('NODE='+n.name+' LINE='+str(n.lineno))
   print((ast.get_source_segment(s,n) or '')[:19000])
PY
echo '===== NETWORK MEMBERSHIP: NO CROSS-STACK ATTACHMENTS ====='
python3 - <<'PY'
import json,subprocess
def get(name):
 return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
e=['aiops2-e2e-v1-aiops2-worker-1','aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-policy-1','aiops2-e2e-v1-aiops2-evidence-1']
p=['aiops2-rebuild-worker','aiops2-rebuild-core','aiops2-rebuild-temporal']
en=set();pn=set()
for name in e:
 o=get(name);ns=set(o['NetworkSettings']['Networks']);en|=ns
 print('E2E='+name+' RUNNING='+str(o['State']['Running']).lower()+' NETWORKS='+','.join(sorted(ns)))
for name in p:
 o=get(name);ns=set(o['NetworkSettings']['Networks']);pn|=ns
 print('PROD='+name+' RUNNING='+str(o['State']['Running']).lower()+' NETWORKS='+','.join(sorted(ns)))
overlap=en&pn
print('CROSS_STACK_NETWORKS='+(','.join(sorted(overlap)) if overlap else 'NONE'))
assert not overlap,'E2E and production share network'
print('NETWORK_SEPARATION=PASS')
PY
echo '===== TEST ENDPOINT / SERVICE PRESENCE ====='
python3 - <<'PY'
import json,subprocess
x=json.loads(subprocess.check_output(['docker','ps','--format','{{json .}}']).decode().replace('}\n{','},{').join([])) if False else []
for line in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if line.startswith('aiops2-e2e-v1-'):print('E2E_CONTAINER='+line)
PY
echo '===== SAFETY ====='
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'CONTAINERS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.984 ====='
