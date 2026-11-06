#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.971 | WORKER REBUILD PROVENANCE ====='
echo '===== 1. IMAGE METADATA ====='
docker image inspect aiops2-worker:fs-demo-candidate-20261105 --format 'IMAGE_ID={{.Id}} CREATED={{.Created}}'
docker image inspect aiops2-worker:fs-demo-candidate-20261105 --format '{{json .Config.Labels}}'
echo '===== 2. CANDIDATE BUILD FILES ====='
for d in /home/aiops/aiops2-v2-delivery /home/aiops/aiops2-fs-demo-source /home/aiops/aiops2-patches/fs-portal-v30/build; do
 echo "SOURCE_ROOT=$d"
 find "$d" -maxdepth 4 -type f \( -name 'Dockerfile*' -o -name '*compose*.yml' -o -name '*compose*.yaml' \) -print 2>/dev/null | head -35
done
echo '===== 3. WORKER FUNCTION SIGNATURES ====='
python3 - <<'PY'
import ast,hashlib
from pathlib import Path
for base in ('/home/aiops/aiops2-v2-delivery','/home/aiops/aiops2-fs-demo-source','/home/aiops/aiops2-patches/fs-portal-v30/build'):
 p=Path(base)/'app/worker/main.py'
 if not p.is_file(): continue
 s=p.read_text()
 t=ast.parse(s)
 print('FILE='+str(p))
 print('SHA256='+hashlib.sha256(s.encode()).hexdigest())
 for n in t.body:
  if isinstance(n,ast.AsyncFunctionDef) and n.name=='start':
   print('START_LINE='+str(n.lineno))
   print('START_SOURCE='+ast.get_source_segment(s,n)[:2500])
   break
 else: print('START_FUNCTION=NOT_FOUND')
PY
echo '===== SAFETY ====='
echo 'FILES_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.971 ====='
