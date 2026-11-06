#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.977 | CANDIDATE REBUILD PREFLIGHT ====='
ROOT=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate
SOURCE="$ROOT/main.py"
EXPECTED=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
echo "$EXPECTED  $SOURCE" | sha256sum -c -
python3 - "$SOURCE" "$ROOT/Dockerfile" <<'PY'
import ast,sys,pathlib
p=pathlib.Path(sys.argv[1]);docker=pathlib.Path(sys.argv[2]).read_text()
s=p.read_text();t=ast.parse(s)
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(f)==1
src=ast.get_source_segment(s,f[0])
for marker in ('run_id required','run not found','run state verification unavailable','run not executable from'):
 assert marker in src,marker
assert src.index('await asyncio.to_thread(get_json') < src.index('Client.connect(TEMP)')
assert 'COPY main.py /app/worker/main.py' in docker
assert 'RUN python -m py_compile /app/worker/main.py' in docker
print('GUARDS=PASS')
print('DOCKERFILE_COPY=PASS')
PY
echo '===== RUNTIME PRESERVATION ====='
echo 'ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda  /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py' | sha256sum -c -
docker inspect aiops2-rebuild-worker --format 'WORKER_RUNNING={{.State.Running}} IMAGE={{.Config.Image}}'
echo 'BUILD_EXECUTED=NO'
echo 'FILES_MODIFIED=NO'
echo '===== END FS.977 ====='
