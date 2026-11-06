#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.985 | E2E BUSINESS RUN CREATION PREFLIGHT ====='
ROOT=/home/aiops/aiops2-fs-demo-source
SRC="$ROOT/integration/worker-fs-candidate/main.py"
echo "7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b  $SRC" | sha256sum -c -
echo '===== WORKFLOW IMPORTS AND CONFIG ====='
python3 - "$SRC" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
for n in t.body:
 if isinstance(n,(ast.Import,ast.ImportFrom)):
  segment=ast.get_source_segment(s,n) or ''
  if any(x in segment.lower() for x in ('workflow','temporal','shared','worker')):
   print('IMPORT='+segment[:250])
 if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ('worker_main','start','start_run','finish_run'):
  print('FUNCTION='+n.name+' LINE='+str(n.lineno))
  print((ast.get_source_segment(s,n) or '')[:8000])
PY
echo '===== RELEVANT SOURCE FILES ====='
find "$ROOT/app/worker" "$ROOT/integration/worker-fs-candidate" -maxdepth 2 -type f \( -name 'workflow.py' -o -name '*compose*.yml' -o -name '*e2e*.py' \) -print 2>/dev/null || true
echo '===== E2E WORKER IMAGE AND NETWORK ====='
docker inspect aiops2-e2e-v1-aiops2-worker-1 --format 'IMAGE={{.Config.Image}} RUNNING={{.State.Running}} NETWORKS={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
echo '===== E2E API ROUTES (SOURCE ONLY) ====='
python3 - "$ROOT" <<'PY'
import ast,pathlib,sys
root=pathlib.Path(sys.argv[1])
for p in [root/'app/core/main.py',root/'app/portal/main.py',root/'integration/worker-fs-candidate/main.py']:
 if not p.is_file():continue
 print('SOURCE='+str(p.relative_to(root)))
 try:t=ast.parse(p.read_text())
 except SyntaxError:continue
 for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   for d in n.decorator_list:
    if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('post','get','put','patch'):
     if d.args and isinstance(d.args[0],ast.Constant) and isinstance(d.args[0].value,str):
      route=d.args[0].value
      if any(x in route for x in ('runs','demo','scenario','execution','health')):
       print('ROUTE='+d.func.attr.upper()+' '+route+' HANDLER='+n.name)
PY
echo '===== QUALIFICATION SAFETY ====='
echo 'NO_HTTP_WRITES=YES'
echo 'REAL_WORKFLOWS_STARTED=0'
echo 'CONTAINERS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.985 ====='
