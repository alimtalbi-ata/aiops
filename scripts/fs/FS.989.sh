#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.989 | ISOLATED TEMPORAL TASK QUEUE CANDIDATE PATCH ====='
SOURCE=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/main.py
EXPECTED=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
IMAGE=aiops2-worker:fs001d-guard-validated-20261106
QUEUE=fs989-guarded-incident-e2e
[[ -f "$SOURCE" ]] || { echo 'SOURCE_NOT_FOUND'; exit 1; }
echo "$EXPECTED  $SOURCE" | sha256sum -c -
docker image inspect "$IMAGE" >/dev/null
echo '===== VERIFY QUEUE REPLACEMENT SITES ====='
python3 - "$SOURCE" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();t=ast.parse(s)
sites=[]
for n in ast.walk(t):
 if isinstance(n,ast.Call):
  f=ast.get_source_segment(s,n.func) or ''
  if f.endswith('start_workflow') or f=='Worker':
   for k in n.keywords:
    if k.arg=='task_queue' and isinstance(k.value,ast.Constant):
     sites.append((f,k.value.value,n.lineno))
for f,q,line in sites:print(f'QUEUE_SITE={f} LINE={line} VALUE={q}')
assert len(sites)==3 and all(q=='aiops-runner' for _,q,_ in sites),'unexpected queue callsites'
print('QUEUE_SITE_COUNT=3')
PY
echo '===== CREATE EPHEMERAL PATCH ARTIFACT ====='
TMPDIR_FS989="$(mktemp -d /tmp/fs989-guarded.XXXXXXXX)"
trap 'rm -rf "$TMPDIR_FS989"' EXIT
python3 - "$SOURCE" "$TMPDIR_FS989/main.py" <<'PY'
import ast,pathlib,sys
src=pathlib.Path(sys.argv[1]).read_text()
old="task_queue='aiops-runner'"
old2='task_queue="aiops-runner"'
assert src.count(old)==2 and src.count(old2)==1,(src.count(old),src.count(old2))
patched=src.replace(old,"task_queue=os.getenv('AIOPS_TEMPORAL_TASK_QUEUE','aiops-runner')").replace(old2,"task_queue=os.getenv('AIOPS_TEMPORAL_TASK_QUEUE','aiops-runner')")
assert patched.count("task_queue=os.getenv('AIOPS_TEMPORAL_TASK_QUEUE','aiops-runner')")==3
ast.parse(patched)
pathlib.Path(sys.argv[2]).write_text(patched)
print('QUEUE_OVERRIDE_PATCH=PASS')
print('DEFAULT_QUEUE_UNCHANGED=aiops-runner')
PY
python3 -m py_compile "$TMPDIR_FS989/main.py"
echo '===== NO CONTAINER MUTATIONS ====='
echo 'IMAGE_BUILD=NO'
echo 'WORKER_STARTED=NO'
echo 'BUSINESS_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.989 ====='
