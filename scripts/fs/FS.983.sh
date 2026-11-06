#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.983 | INCIDENT WORKFLOW E2E SAFETY PLAN ====='
ROOT=/home/aiops/aiops2-fs-demo-source
SRC="$ROOT/integration/worker-fs-candidate/main.py"
[[ -f "$SRC" ]] || { echo 'SOURCE_MISSING'; exit 1; }
echo '===== SOURCE INTEGRITY ====='
echo '7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b  '"$SRC" | sha256sum -c -
echo '===== WORKFLOW AND ACTIVITIES ====='
python3 - "$SRC" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
for n in t.body:
 if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and (isinstance(n,ast.ClassDef) and 'Workflow' in n.name or getattr(n,'name','') in ('start_run','execute_stage','finish_run')):
  print('NODE='+n.name+' LINE='+str(n.lineno))
  print(ast.get_source_segment(s,n)[:14000])
PY
echo '===== E2E CONTAINER NETWORKS AND SERVICE ALIASES ====='
python3 - <<'PY'
import json,subprocess
names=['aiops2-e2e-v1-aiops2-worker-1','aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-policy-1','aiops2-e2e-v1-aiops2-evidence-1','aiops2-rebuild-worker','aiops2-rebuild-temporal']
for name in names:
 try: obj=json.loads(subprocess.check_output(['docker','inspect',name],stderr=subprocess.DEVNULL))[0]
 except Exception as exc: print('INSPECT_UNAVAILABLE='+name+' '+type(exc).__name__);continue
 nets=obj['NetworkSettings']['Networks']
 print('CONTAINER='+name+' IMAGE='+obj['Config']['Image']+' RUNNING='+str(obj['State']['Running']).lower())
 for net,details in nets.items(): print(' NETWORK='+net+' ALIASES='+','.join(details.get('Aliases') or []))
 mounts=obj.get('Mounts') or []
 for m in mounts:
  print(' MOUNT_TYPE='+m['Type']+' TARGET='+m['Destination']+' READONLY='+str(not m['RW']).lower())
PY
echo '===== E2E SCRIPT PREVIEW: SIDE EFFECTS ====='
for file in "$ROOT/tests/runtime-e2e.sh" "$ROOT/tests/synthetic-e2e.sh" "$ROOT/tests/evidence-e2e.sh"; do
 if [[ -f "$file" ]]; then
  echo "SCRIPT=$(basename "$file")"
  python3 - "$file" <<'PY'
import sys
for n,line in enumerate(open(sys.argv[1]),1):
 if any(x in line.lower() for x in ('docker compose','curl ','psqlc ','/api/demo','/api/execution','/api/runs','evidence','policy','effect','run_id')):
  if any(x in line.lower() for x in ('token','secret','password','authorization','bearer','env-file')): continue
  print(f'{n}: {line.rstrip()[:160]}')
PY
 fi
done
echo '===== SAFETY ====='
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'CONTAINERS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.983 ====='
