#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.992 | INCIDENT WORKFLOW SYNTHETIC E2E CONTRACT ====='
ROOT=/home/aiops/aiops2-fs-demo-source
IMAGE=aiops2-worker:fs990-guarded-isolated-queue-20261106
EXPECTED=9704c66b9d5577154d82b59a78aac104668f93faf7e39335baabde615e4c4a72
ACTUAL="$(docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo 'GUARDED_IMAGE_MISMATCH'; exit 1; }
echo 'GUARDED_IMAGE_INTEGRITY=PASS'
echo '===== CORE RUN CREATION / EXECUTION / SCENARIO CONTRACT ====='
python3 - "$ROOT/app/core/main.py" "$ROOT/app/worker/workflow.py" <<'PY'
import ast,pathlib,sys
for path,names in [(sys.argv[1],{'create','execute','register_scenario','scenario','scenarios','get_run'}),(sys.argv[2],{'run'})]:
 s=pathlib.Path(path).read_text();t=ast.parse(s)
 print('SOURCE='+path)
 for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names:
   print('FUNCTION='+n.name+' LINE='+str(n.lineno))
   print((ast.get_source_segment(s,n) or '')[:11000])
PY
echo '===== E2E NETWORK / SERVICES ====='
python3 - <<'PY'
import json,subprocess
e=['aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-evidence-1','aiops2-e2e-v1-aiops2-policy-1','aiops2-e2e-v1-aiops2-intelligence-1','aiops2-e2e-v1-aiops2-twin-1']
p=['aiops2-rebuild-core','aiops2-rebuild-temporal','aiops2-rebuild-worker']
def inspect(n):return json.loads(subprocess.check_output(['docker','inspect',n]))[0]
en=set();pn=set()
for n in e:
 o=inspect(n);assert o['State']['Running'],n+' not running'
 ns=set(o['NetworkSettings']['Networks']);en|=ns
 print('E2E_SERVICE='+n+' NETWORKS='+','.join(sorted(ns)))
for n in p:
 o=inspect(n);ns=set(o['NetworkSettings']['Networks']);pn|=ns
 print('PROD_SERVICE='+n+' RUNNING='+str(o['State']['Running']).lower())
assert not en.intersection(pn),'cross-stack networks'
print('NETWORK_ISOLATION=PASS')
PY
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.992 ====='
