#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.997 | BUILD DEMO REMEDIATION GATE HARDENING ====='
SOURCE=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/main.py
BASE=aiops2-worker:fs990-guarded-isolated-queue-20261106
TARGET=aiops2-worker:fs997-demo-gate-hardened-20261106
EXPECTED_SOURCE=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
EXPECTED_BASE=9704c66b9d5577154d82b59a78aac104668f93faf7e39335baabde615e4c4a72
echo "$EXPECTED_SOURCE  $SOURCE" | sha256sum -c -
ACTUAL="$(docker run --rm --network none --entrypoint python "$BASE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$ACTUAL" == "$EXPECTED_BASE" ]] || { echo 'BASE_IMAGE_MISMATCH'; exit 1; }
DIR="$(mktemp -d /tmp/fs997.XXXXXXXX)"
trap 'rm -rf "$DIR"' EXIT
python3 - "$SOURCE" "$DIR/main.py" <<'PY'
import ast,pathlib,sys
source=pathlib.Path(sys.argv[1]).read_text()
old="        synthetic=True\n"
assert source.count(old)==1,'unexpected synthetic marker count'
guard="""        if stage in ('REMEDIATE','VERIFY'):
            detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
            run=detail.get('run') or {}
            gates=[g for g in detail.get('gates',[]) if g.get('stage')=='POLICY']
            authorized=(mode=='DEMO' and run.get('mode')=='DEMO'
                and run.get('scenario_id')==scenario
                and any(g.get('state')=='PASS' and g.get('decision')=='SIMULATE'
                        for g in gates))
            if not authorized:
                raise RuntimeError('demo_remediation_requires_policy_simulate')
"""
patched=source.replace(old,guard+old)
queue_old1="task_queue='aiops-runner'"
queue_old2='task_queue="aiops-runner"'
assert patched.count(queue_old1)==2 and patched.count(queue_old2)==1
replacement="task_queue=os.getenv('AIOPS_TEMPORAL_TASK_QUEUE','aiops-runner')"
patched=patched.replace(queue_old1,replacement).replace(queue_old2,replacement)
tree=ast.parse(patched)
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_execute_stage_blocking')
guards=[n for n in ast.walk(fn) if isinstance(n,ast.Raise) and 'demo_remediation_requires_policy_simulate' in (ast.get_source_segment(patched,n) or '')]
assert len(guards)==1
out=pathlib.Path(sys.argv[2]);out.write_text(patched)
import hashlib
print('PATCHED_SOURCE_SHA256='+hashlib.sha256(out.read_bytes()).hexdigest())
print('REMEDIATION_GATE_CHECK=INSTALLED')
print('TEMPORAL_QUEUE_OVERRIDE_SITES=3')
PY
cat > "$DIR/Dockerfile" <<'DOCKER'
FROM aiops2-worker:fs990-guarded-isolated-queue-20261106
COPY main.py /app/worker/main.py
RUN python -m py_compile /app/worker/main.py
DOCKER
docker build --network none --tag "$TARGET" "$DIR"
echo '===== STATIC RUNTIME INTEGRITY ====='
docker run --rm --network none --entrypoint python "$TARGET" -c 'import ast,pathlib; s=pathlib.Path("/app/worker/main.py").read_text();ast.parse(s);assert "demo_remediation_requires_policy_simulate" in s;print("HARDENED_IMAGE=PASS")'
echo "CANDIDATE_IMAGE=$TARGET"
echo 'WORKER_SERVICE_STARTED=NO'
echo 'BUSINESS_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.997 ====='
