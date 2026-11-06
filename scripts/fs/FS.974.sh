#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.974 | CANDIDATE BUILD MAIN.PY AUDIT ====='
ROOT=/home/aiops/aiops2-fs-demo-source
CTX="$ROOT/integration/worker-fs-candidate"
echo '===== 1. BUILD CONTEXT ====='
for f in "$CTX/main.py" "$CTX/Dockerfile" "$ROOT/app/worker/main.py" /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py; do
 echo "FILE=$f"
 if [[ -f "$f" ]]; then
  sha256sum "$f"
  stat -c 'SIZE=%s MODIFIED=%y' "$f"
 else echo 'MISSING'; fi
done
echo '===== 2. CANDIDATE GUARD STATUS ====='
python3 - "$CTX/main.py" <<'PY'
import ast,sys
from pathlib import Path
p=Path(sys.argv[1])
if not p.is_file(): print('CANDIDATE_MAIN_MISSING=YES');raise SystemExit(0)
s=p.read_text();t=ast.parse(s)
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
print('START_FUNCTION_COUNT='+str(len(f)))
if len(f)==1:
 src=ast.get_source_segment(s,f[0])
 for marker in ('run_id required','run not found','run state verification unavailable','run not executable from'):
  print('GUARD_'+marker.replace(' ','_').upper()+'='+str(marker in src))
 print('CORE_CHECK_BEFORE_TEMPORAL='+str('await asyncio.to_thread(get_json' in src and src.index('await asyncio.to_thread(get_json')<src.index('Client.connect(TEMP)')))
PY
echo '===== 3. BUILD REFERENCES ====='
grep -R -n -E 'worker-fs-candidate|fs-demo-candidate-20261105|docker build' "$ROOT/integration" 2>/dev/null | head -60 || true
echo '===== SAFETY ====='
echo 'FILES_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
echo '===== END FS.974 ====='
