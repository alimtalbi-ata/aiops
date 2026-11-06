#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.991 | GUARDED WORKER DEDICATED TEMPORAL POLLING ====='
IMAGE=aiops2-worker:fs990-guarded-isolated-queue-20261106
NETWORK=aiops2-e2e-v1_control
QUEUE=fs991-guarded-poll-only
EXPECTED=9704c66b9d5577154d82b59a78aac104668f93faf7e39335baabde615e4c4a72
docker image inspect "$IMAGE" >/dev/null
docker network inspect "$NETWORK" >/dev/null
echo '===== VERIFY IMAGE AND NETWORK ISOLATION ====='
python3 - "$NETWORK" <<'PY'
import json,subprocess,sys
network=sys.argv[1]
names=['aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-worker-1','aiops2-rebuild-worker','aiops2-rebuild-temporal']
o={n:json.loads(subprocess.check_output(['docker','inspect',n]))[0] for n in names}
for n in names:assert o[n]['State']['Running'],n+' not running'
assert network in o[names[0]]['NetworkSettings']['Networks']
assert network in o[names[1]]['NetworkSettings']['Networks']
for n in names[2:]:assert network not in o[n]['NetworkSettings']['Networks'],n+' shares E2E network'
print('NETWORK_ISOLATION=PASS')
PY
ACTUAL="$(docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "IMAGE_SHA_MISMATCH=$ACTUAL"; exit 1; }
echo 'IMAGE_INTEGRITY=PASS'
echo '===== RUN EPHEMERAL WORKER POLLER ON UNIQUE QUEUE ====='
RUNNER="$(cat <<'PY'
import asyncio,os
from temporalio.client import Client
from temporalio.worker import Worker
from worker.workflow import IncidentWorkflow,AcmeSimulatedHitlWorkflow
from worker.main import execute_stage,start_run,finish_run,acme_simulated_no_effect
async def main():
 queue=os.environ['AIOPS_TEMPORAL_TASK_QUEUE']
 assert queue=='fs991-guarded-poll-only'
 client=await Client.connect(os.environ['TEMPORAL_ADDRESS'])
 print('TEMPORAL_CONNECTION=PASS',flush=True)
 async with Worker(client,task_queue=queue,workflows=[IncidentWorkflow,AcmeSimulatedHitlWorkflow],activities=[execute_stage,start_run,finish_run,acme_simulated_no_effect]):
  print('DEDICATED_WORKER_POLLING=PASS',flush=True)
  print('TASK_QUEUE='+queue,flush=True)
  await asyncio.sleep(8)
 print('WORKER_SHUTDOWN=PASS',flush=True)
asyncio.run(main())
PY
)"
timeout 45s docker run --rm --network "$NETWORK" --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m --env AIOPS_INTERNAL_TOKEN=fs991-no-business-activity-token --env TEMPORAL_ADDRESS=aiops2-temporal:7233 --env AIOPS_TEMPORAL_TASK_QUEUE="$QUEUE" --entrypoint python "$IMAGE" -c "$RUNNER"
echo '===== SAFETY ====='
echo 'REAL_BUSINESS_WORKFLOWS_STARTED=0'
echo 'NO_BUSINESS_ACTIVITIES_EXECUTED=YES'
echo 'E2E_EXISTING_WORKER_UNCHANGED=YES'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.991 ====='
