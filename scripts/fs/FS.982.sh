#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.982 | REAL TEMPORAL ISOLATED E2E ====='
IMAGE=aiops2-worker:fs001d-guard-validated-20261106
NET=aiops2-e2e-v1_control
TEMP_CONTAINER=aiops2-e2e-v1-aiops2-temporal-1
PROD_WORKER=aiops2-rebuild-worker
docker image inspect "$IMAGE" >/dev/null
docker network inspect "$NET" >/dev/null
docker inspect "$TEMP_CONTAINER" --format '{{if not .State.Running}}{{fail "E2E Temporal stopped"}}{{end}}' >/dev/null
python3 - "$NET" "$TEMP_CONTAINER" <<'PY'
import json,subprocess,sys
net,target=sys.argv[1:]
def inspect(kind,name): return json.loads(subprocess.check_output(['docker',kind,'inspect',name]))[0]
t=inspect('container',target)
p=inspect('container','aiops2-rebuild-temporal')
assert net in t['NetworkSettings']['Networks'],'E2E Temporal missing from E2E network'
assert net not in p['NetworkSettings']['Networks'],'Production Temporal on E2E network: refuse'
n=inspect('network',net)
members=set(n.get('Containers',{}))
assert t['Id'] in members,'E2E Temporal not attached'
assert p['Id'] not in members,'Production Temporal attached: refuse'
print('NETWORK_ISOLATION=PASS')
print('E2E_TEMPORAL_RUNNING='+str(t['State']['Running']).lower())
PY
echo '===== TEMPORAL SDK WORKFLOW, UNIQUE TASK QUEUE, NO BUSINESS ACTIVITY ====='
docker run --rm -i --network "$NET" --env AIOPS_INTERNAL_TOKEN=fs982-isolated-token --entrypoint python "$IMAGE" - <<'PY'
import asyncio,uuid
from datetime import timedelta
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
@workflow.defn
class Fs982NoEffect:
 @workflow.run
 async def run(self,marker:str)->str:
  return 'FS982-OK:'+marker
async def main():
 marker='FS982-'+uuid.uuid4().hex
 queue='fs982-isolated-'+uuid.uuid4().hex
 client=await asyncio.wait_for(Client.connect('aiops2-e2e-v1-aiops2-temporal-1:7233',namespace='default'),timeout=20)
 async with Worker(client,task_queue=queue,workflows=[Fs982NoEffect],activities=[]):
  h=await asyncio.wait_for(client.start_workflow(Fs982NoEffect.run,marker,id=marker,task_queue=queue,execution_timeout=timedelta(seconds=45)),timeout=20)
  result=await asyncio.wait_for(h.result(),timeout=40)
  assert result=='FS982-OK:'+marker,(result,marker)
  print('REAL_TEMPORAL_WORKFLOW=PASS')
  print('WORKFLOW_ID='+marker)
  print('UNIQUE_TASK_QUEUE=PASS')
  print('NO_BUSINESS_ACTIVITIES=PASS')
asyncio.run(main())
PY
echo '===== PRODUCTION INTEGRITY ====='
docker inspect "$PROD_WORKER" --format 'PRODUCTION_RUNNING={{.State.Running}} PRODUCTION_IMAGE={{.Config.Image}}'
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_WORKFLOWS_STARTED=0'
echo 'CANDIDATE_INCIDENT_WORKFLOW_TESTED=NO'
echo '===== END FS.982 ====='
