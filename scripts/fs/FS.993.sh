#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.993 | GUARDED INCIDENT WORKFLOW E2E FAIL-CLOSED ====='
IMAGE=aiops2-worker:fs990-guarded-isolated-queue-20261106
EXPECTED=9704c66b9d5577154d82b59a78aac104668f93faf7e39335baabde615e4c4a72
NETWORK=aiops2-e2e-v1_control
QUEUE=fs993-guarded-incident
CORE_CONTAINER=aiops2-e2e-v1-aiops2-core-1
[[ "$(docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')" == "$EXPECTED" ]] || { echo 'IMAGE_INTEGRITY=FAIL'; exit 1; }
python3 - <<'PY'
import json,subprocess
names=['aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-worker-1']
for n in names:
 o=json.loads(subprocess.check_output(['docker','inspect',n]))[0]
 assert o['State']['Running'] and 'aiops2-e2e-v1_control' in o['NetworkSettings']['Networks'],n
for n in ['aiops2-rebuild-core','aiops2-rebuild-temporal','aiops2-rebuild-worker']:
 o=json.loads(subprocess.check_output(['docker','inspect',n]))[0]
 assert 'aiops2-e2e-v1_control' not in o['NetworkSettings']['Networks'],n
print('NETWORK_ISOLATION=PASS')
PY
echo '===== RUN ONE REAL WORKFLOW WITH LIVE FAIL-CLOSED GUARD ====='
echo 'TEST_MODE=LIVE (synthetic test run; no LIVE adapters invoked)'
echo 'EXPECTED_OUTCOME=BLOCKED at NORMALIZE'
# The token stays inside E2E Core container; it is never printed or passed as a host argument.
# This driver is injected through stdin and invokes Docker from inside the host only for the
# worker. Its Core API writes are limited to an isolated test run.
WORKDIR="$(mktemp -d /tmp/fs993.XXXXXXXX)"
chmod 700 "$WORKDIR"
trap 'rm -rf "$WORKDIR"' EXIT
cat > "$WORKDIR/runner.py" <<'PY'
import asyncio,json,os,uuid,urllib.request,urllib.error
from temporalio.client import Client
from temporalio.worker import Worker
from worker.workflow import IncidentWorkflow
from worker.main import start_run,execute_stage,finish_run
TOKEN=os.environ['AIOPS_INTERNAL_TOKEN']
CORE='http://aiops2-core:810'
def call(method,path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(CORE+path,data=data,method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
async def main():
 key='FS993-'+uuid.uuid4().hex
 run=await asyncio.to_thread(call,'POST','/api/runs',{'mode':'LIVE','scenario_id':'FS993-FAIL-CLOSED','idempotency_key':key})
 assert run['status']=='CREATED' and run['version']==1,run
 rid=run['run_id']
 print('ISOLATED_TEST_RUN_ID='+rid,flush=True)
 client=await Client.connect('aiops2-temporal:7233')
 queue=os.environ['AIOPS_TEMPORAL_TASK_QUEUE']
 async with Worker(client,task_queue=queue,workflows=[IncidentWorkflow],activities=[start_run,execute_stage,finish_run]):
  handle=await client.start_workflow(IncidentWorkflow.run,{'run_id':rid,'mode':'LIVE','scenario_id':'FS993-FAIL-CLOSED','version':1},id=rid,task_queue=queue)
  print('REAL_INCIDENT_WORKFLOW_STARTED=YES',flush=True)
  result=await asyncio.wait_for(handle.result(),timeout=90)
  detail=await asyncio.to_thread(call,'GET','/api/runs/'+rid)
  status=detail['run']['status']
  events=detail.get('events',[])
  print('TEMPORAL_RESULT_STATUS='+str(result.get('status')),flush=True)
  print('CORE_RUN_STATUS='+status,flush=True)
  print('LIVE_ADAPTER_UNAVAILABLE_EVENTS='+str(sum(x.get('event_type')=='LIVE_ADAPTER_UNAVAILABLE' for x in events)),flush=True)
  print('STAGES_REACHED='+','.join(dict.fromkeys(x.get('stage','') for x in events)),flush=True)
  assert result.get('status')=='BLOCKED' and status=='BLOCKED','fail-closed invariant failed'
  assert any(x.get('event_type')=='LIVE_ADAPTER_UNAVAILABLE' for x in events),'guard event missing'
  assert not any(x.get('stage') in ('REMEDIATE','VERIFY') for x in events),'unsafe downstream stage reached'
  print('REAL_INCIDENT_WORKFLOW_FAIL_CLOSED=PASS',flush=True)
asyncio.run(main())
PY
# Obtain token via docker exec only as a temporary file; never echo it.
docker exec "$CORE_CONTAINER" python -c 'import os,sys; v=os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("ADMIN_TOKEN"); sys.stdout.write(v or ""); sys.exit(0 if v else 1)' > "$WORKDIR/token"
chmod 600 "$WORKDIR/token"
[[ -s "$WORKDIR/token" ]] || { echo 'E2E_TOKEN_MISSING'; exit 1; }
# Token is supplied via Docker env-file, not as a visible command-line argument.
printf 'AIOPS_INTERNAL_TOKEN=%s\n' "$(cat "$WORKDIR/token")" > "$WORKDIR/env"
chmod 600 "$WORKDIR/env"
printf 'AIOPS_TEMPORAL_TASK_QUEUE=%s\nCORE_URL=http://aiops2-core:810\nTEMPORAL_ADDRESS=aiops2-temporal:7233\n' "$QUEUE" >> "$WORKDIR/env"
timeout 150s docker run --rm --network "$NETWORK" --env-file "$WORKDIR/env" --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m --mount "type=bind,src=$WORKDIR/runner.py,dst=/tmp/fs993_runner.py,readonly" --entrypoint python "$IMAGE" /tmp/fs993_runner.py
echo '===== SAFETY ====='
echo 'PRODUCTION_RESTARTED=NO'
echo 'EXISTING_E2E_WORKER_UNCHANGED=YES'
echo '===== END FS.993 ====='
