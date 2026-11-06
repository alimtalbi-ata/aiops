#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.979 | WORKFLOW AND E2E DISCOVERY ====='
ROOT=/home/aiops/aiops2-fs-demo-source
F="$ROOT/integration/worker-fs-candidate/main.py"
EXPECTED=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
echo "$EXPECTED  $F" | sha256sum -c -
echo '===== 1. ROUTES, WORKFLOW, EXTERNAL CALLS ====='
python3 - "$F" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
for node in ast.walk(t):
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
  dec=[ast.get_source_segment(s,d) or '' for d in node.decorator_list]
  if any('app.' in d or 'workflow.' in d or 'activity.' in d for d in dec) or node.name in ('start','run'):
   print(f'FUNCTION={node.name} LINE={node.lineno} DECORATORS={dec}')
   if node.name in ('start','run'):
    src=ast.get_source_segment(s,node) or ''
    print('BODY_BEGIN');print(src[:12000]);print('BODY_END')
for node in t.body:
 if isinstance(node,(ast.Assign,ast.AnnAssign)):
  txt=ast.get_source_segment(s,node) or ''
  if any(x in txt for x in ('CORE','TEMP','ADMIN','API','URL','TOKEN')):
   print('CONFIG_DECL='+txt[:350].replace('\n',' '))
PY
echo '===== 2. TEST AND COMPOSE FILE INVENTORY ====='
for dir in "$ROOT/integration" "$ROOT/tests" /home/aiops/aiops2-v2-delivery/tests; do
 if [[ -d "$dir" ]]; then
  find "$dir" -maxdepth 4 -type f \( -iname '*e2e*' -o -iname '*workflow*' -o -iname '*compose*' -o -iname '*test*' \) -print | sed -n '1,100p'
 fi
done
echo '===== 3. CONTAINER INVENTORY ====='
docker ps --format 'NAME={{.Names}} IMAGE={{.Image}} STATUS={{.Status}}'
echo '===== 4. IMAGE RUNTIME METADATA ====='
docker image inspect aiops2-worker:fs001d-guard-validated-20261106 --format 'IMAGE_ID={{.Id}} CMD={{json .Config.Cmd}} ENTRYPOINT={{json (index .Config "Entrypoint")}} EXPOSED={{json (index .Config "ExposedPorts")}}'
echo '===== SAFETY ====='
echo 'WORKFLOWS_STARTED=0'
echo 'CONTAINERS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo 'FILES_MODIFIED=NO'
echo '===== END FS.979 ====='
