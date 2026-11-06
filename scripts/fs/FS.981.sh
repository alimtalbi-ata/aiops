#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.981 | TEMPORAL REAL E2E ISOLATION PREFLIGHT ====='
IMAGE=aiops2-worker:fs001d-guard-validated-20261106
docker image inspect "$IMAGE" >/dev/null
echo '===== PRODUCTION WORKER CONFIG (REDACTED) ====='
docker inspect aiops2-rebuild-worker --format 'RUNNING={{.State.Running}} IMAGE={{.Config.Image}} NETWORKS={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
echo '===== CANDIDATE WORKER CONFIG ====='
docker image inspect "$IMAGE" --format 'IMAGE_ID={{.Id}} CMD={{json (index .Config "Cmd")}}'
echo '===== E2E STACK NETWORKS ====='
for name in aiops2-e2e-v1-aiops2-worker-1 aiops2-e2e-v1-aiops2-core-1 aiops2-e2e-v1-aiops2-temporal-1 aiops2-rebuild-core aiops2-rebuild-temporal; do
 if docker container inspect "$name" >/dev/null 2>&1; then
  docker inspect "$name" --format 'CONTAINER={{.Name}} RUNNING={{.State.Running}} NETWORKS={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
 else
  echo "CONTAINER_MISSING=$name"
 fi
done
echo '===== TEST HARNESS ENTRYPOINTS (READ-ONLY) ====='
ROOT=/home/aiops/aiops2-fs-demo-source
for rel in tests/runtime-e2e.sh tests/synthetic-e2e.sh tests/evidence-e2e.sh tests/test_worker_acme_simulated_hitl.py tests/test_debian_acme_sim_e2e.py integration/worker-fs-candidate/compose.fs-worker.yml; do
 p="$ROOT/$rel"
 if [[ -f "$p" ]]; then
  echo "FILE=$rel"
  python3 - "$p" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1])
lines=p.read_text(errors='replace').splitlines()
for i,line in enumerate(lines[:180],1):
 if any(x in line.lower() for x in ('docker','pytest','curl','temporal','workflow','run_id','sandbox','network','port','command','health','e2e','api/execution','api/runs','create','delete','cleanup','token','secret','password')):
  red=line
  for word in ('token','secret','password'):
   if word in line.lower() and ('=' in line or ':' in line):
    red='[REDACTED CONFIG LINE]'
    break
  print(f'{i}: {red[:180]}')
PY
 fi
done
echo '===== TEMPORAL WORKFLOW AST SUMMARY ====='
python3 - "$ROOT/integration/worker-fs-candidate/main.py" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
for n in ast.walk(t):
 if isinstance(n,ast.ClassDef) and 'Workflow' in n.name:
  print('WORKFLOW_CLASS='+n.name)
  for fn in n.body:
   if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
    print('METHOD='+fn.name+' LINE='+str(fn.lineno))
for n in ast.walk(t):
 if isinstance(n,ast.Call):
  x=ast.get_source_segment(s,n.func) or ''
  if any(y in x for y in ('execute_activity','start_workflow','execute_workflow','Worker(')):
   print('CALL='+x[:120]+' LINE='+str(n.lineno))
PY
echo '===== SAFETY ====='
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'CONTAINERS_STARTED=0'
echo 'FILES_MODIFIED=NO'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.981 ====='
