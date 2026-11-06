#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.990 | BUILD GUARDED WORKER WITH ISOLATED TASK QUEUE ====='
SOURCE=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/main.py
EXPECTED=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
BASE=aiops2-worker:fs001d-guard-validated-20261106
TARGET=aiops2-worker:fs990-guarded-isolated-queue-20261106
[[ -f "$SOURCE" ]] || { echo 'SOURCE_MISSING'; exit 1; }
echo "$EXPECTED  $SOURCE" | sha256sum -c -
docker image inspect "$BASE" >/dev/null
echo '===== VERIFY BASE IMAGE SOURCE ====='
BASE_SHA="$(docker run --rm --network none --entrypoint python "$BASE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$BASE_SHA" == "$EXPECTED" ]] || { echo "BASE_SOURCE_MISMATCH=$BASE_SHA"; exit 1; }
echo 'BASE_SOURCE_INTEGRITY=PASS'
TMPDIR_FS990="$(mktemp -d /tmp/fs990-image.XXXXXXXX)"
trap 'rm -rf "$TMPDIR_FS990"' EXIT
echo '===== PATCH EPHEMERAL BUILD CONTEXT ====='
python3 - "$SOURCE" "$TMPDIR_FS990/main.py" "$TMPDIR_FS990/expected.sha" <<'PY'
import ast,hashlib,pathlib,sys
source=pathlib.Path(sys.argv[1]).read_text()
t=ast.parse(source)
sites=[]
for node in ast.walk(t):
 if isinstance(node,ast.Call):
  fn=ast.get_source_segment(source,node.func) or ''
  if fn.endswith('start_workflow') or fn=='Worker':
   for kw in node.keywords:
    if kw.arg=='task_queue' and isinstance(kw.value,ast.Constant):
     sites.append((fn,kw.value.value))
assert len(sites)==3 and all(v=='aiops-runner' for _,v in sites),sites
old1="task_queue='aiops-runner'"
old2='task_queue="aiops-runner"'
assert source.count(old1)==2 and source.count(old2)==1
replacement="task_queue=os.getenv('AIOPS_TEMPORAL_TASK_QUEUE','aiops-runner')"
patched=source.replace(old1,replacement).replace(old2,replacement)
assert patched.count(replacement)==3
ast.parse(patched)
out=pathlib.Path(sys.argv[2]);out.write_text(patched)
digest=hashlib.sha256(out.read_bytes()).hexdigest()
pathlib.Path(sys.argv[3]).write_text(digest+'\n')
print('PATCHED_SOURCE_SHA256='+digest)
print('QUEUE_OVERRIDE_SITES=3')
print('DEFAULT_TASK_QUEUE=aiops-runner')
PY
cat > "$TMPDIR_FS990/Dockerfile" <<'DOCKER'
FROM aiops2-worker:fs001d-guard-validated-20261106
COPY main.py /app/worker/main.py
RUN python -m py_compile /app/worker/main.py
DOCKER
echo '===== BUILD CANDIDATE IMAGE ====='
docker build --network none --tag "$TARGET" "$TMPDIR_FS990"
echo '===== VERIFY IMAGE CONTENT AND CONFIG ====='
EXPECTED_PATCHED_SHA="$(cat "$TMPDIR_FS990/expected.sha")"
ACTUAL_PATCHED_SHA="$(docker run --rm --network none --entrypoint python "$TARGET" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$EXPECTED_PATCHED_SHA" == "$ACTUAL_PATCHED_SHA" ]] || { echo 'BUILT_SOURCE_MISMATCH'; exit 1; }
echo "BUILT_IMAGE_SOURCE_SHA256=$ACTUAL_PATCHED_SHA"
docker run --rm --network none --env AIOPS_INTERNAL_TOKEN=fs990-offline-test-token --env AIOPS_TEMPORAL_TASK_QUEUE=fs990-isolated-check --entrypoint python "$TARGET" -c '
import ast,pathlib
s=pathlib.Path("/app/worker/main.py").read_text()
t=ast.parse(s)
matches=[]
for n in ast.walk(t):
 if isinstance(n,ast.Call):
  for k in n.keywords:
   if k.arg=="task_queue": matches.append(k.value)
assert len(matches)==3
assert all(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=="getenv" for x in matches)
print("IMAGE_QUEUE_OVERRIDE=PASS")
'
echo '===== SAFETY ====='
echo "CANDIDATE_IMAGE=$TARGET"
echo 'IMAGE_BUILD=PASS'
echo 'WORKER_SERVICE_STARTED=NO'
echo 'BUSINESS_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.990 ====='
