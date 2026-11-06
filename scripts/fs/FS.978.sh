#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.978 | ISOLATED CANDIDATE IMAGE BUILD ====='
CTX=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate
SOURCE="$CTX/main.py"
SOURCE_SHA=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
TAG=aiops2-worker:fs001d-guard-validated-20261106
echo "$SOURCE_SHA  $SOURCE" | sha256sum -c -
python3 - "$SOURCE" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(f)==1
src=ast.get_source_segment(s,f[0])
for marker in ('run_id required','run not found','run state verification unavailable','run not executable from'):
 assert marker in src,marker
assert src.index('await asyncio.to_thread(get_json')<src.index('Client.connect(TEMP)')
print('PREBUILD_GUARDS=PASS')
PY
if docker image inspect "$TAG" >/dev/null 2>&1; then
 echo "REFUSED_EXISTING_IMAGE_TAG=$TAG"
 exit 1
fi
echo '===== BUILD NEW IMAGE (NO CONTAINER START) ====='
docker build --pull=false --no-cache -t "$TAG" "$CTX"
echo '===== VERIFY EMBEDDED SOURCE ====='
docker run --rm --network none --entrypoint python "$TAG" -c '
import ast,hashlib,pathlib
p=pathlib.Path("/app/worker/main.py")
s=p.read_text()
t=ast.parse(s)
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="start"]
assert len(f)==1
src=ast.get_source_segment(s,f[0])
for marker in ("run_id required","run not found","run state verification unavailable","run not executable from"):
 assert marker in src,marker
assert src.index("await asyncio.to_thread(get_json")<src.index("Client.connect(TEMP)")
expected="7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b"
actual=hashlib.sha256(p.read_bytes()).hexdigest()
print("IMAGE_SOURCE_SHA256="+actual)
assert actual==expected
print("IMAGE_GUARDS=PASS")
'
echo '===== PRODUCTION INTEGRITY ====='
echo 'ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda  /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py' | sha256sum -c -
docker inspect aiops2-rebuild-worker --format 'PRODUCTION_RUNNING={{.State.Running}} PRODUCTION_IMAGE={{.Config.Image}}'
echo "NEW_IMAGE=$TAG"
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.978 ====='
