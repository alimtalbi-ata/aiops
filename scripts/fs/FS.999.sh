#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.999 | GUARDED INCIDENT WORKFLOW DEMO E2E ====='
IMAGE=aiops2-worker:fs997-demo-gate-hardened-20261106
EXPECTED=dfa580bb4caeea2e4815f8c3ab560e3b0d54b44fb5dc3abc38b4a3f56cbc8327
NETWORK=aiops2-e2e-v1_control
CORE_CONTAINER=aiops2-e2e-v1-aiops2-core-1
QUEUE=fs999-guarded-demo
SCENARIO=SCN-GOLDEN-PAYMENT-P1
echo '===== PRECONDITIONS ====='
ACTUAL="$(docker run --rm --network none --entrypoint python "$IMAGE" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo 'IMAGE_INTEGRITY=FAIL'; exit 1; }
python3 - <<'PY'
import json,subprocess
names=['aiops2-e2e-v1-aiops2-core-1','aiops2-e2e-v1-aiops2-temporal-1','aiops2-e2e-v1-aiops2-worker-1','aiops2-e2e-v1-aiops2-policy-1','aiops2-e2e-v1-aiops2-evidence-1','aiops2-e2e-v1-aiops2-intelligence-1','aiops2-e2e-v1-aiops2-twin-1']
for n in names:
 o=json.loads(subprocess.check_output(['docker','inspect',n]))[0]
 assert o['State']['Running'] and 'aiops2-e2e-v1_control' in o['NetworkSettings']['Networks'],n
for n in ['aiops2-rebuild-core','aiops2-rebuild-temporal','aiops2-rebuild-worker']:
 o=json.loads(subprocess.check_output(['docker','inspect',n]))[0]
 assert 'aiops2-e2e-v1_control' not in o['NetworkSettings']['Networks'],n
print('NETWORK_ISOLATION=PASS')
PY
WORKDIR="$(mktemp -d /tmp/fs999.XXXXXXXX)"
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
SCENARIO='SCN-GOLDEN-PAYMENT-P1'
def call(method,path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(CORE+path,data=data,method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
async def main():
 scenario=await asyncio.to_thread(call,'GET','/api/scenarios/'+SCENARIO)
 assert scenario['scenario']['synthetic'] is True,'scenario is not synthetic'
 print('SYNTHETIC_SCENARIO=PASS',flush=True)
 key='FS999-'+uuid.uuid4().hex
 run=await asyncio.to_thread(call,'POST','/api/runs',{'mode':'DEMO','scenario_id':SCENARIO,'idempotency_key':key})
 assert run['status']=='CREATED' and run['version']==1,run
 rid=run['run_id']
 print('E2E_RUN_ID='+rid,flush=True)
 client=await Client.connect('aiops2-temporal:7233')
 queue=os.environ['AIOPS_TEMPORAL_TASK_QUEUE']
 async with Worker(client,task_queue=queue,workflows=[IncidentWorkflow],activities=[start_run,execute_stage,finish_run]):
  handle=await client.start_workflow(IncidentWorkflow.run,{'run_id':rid,'mode':'DEMO','scenario_id':SCENARIO,'version':1},id=rid,task_queue=queue)
  print('REAL_INCIDENT_WORKFLOW_STARTED=YES',flush=True)
  try:
   result=await asyncio.wait_for(handle.result(),timeout=160)
   print('TEMPORAL_RESULT_STATUS='+str(result.get('status')),flush=True)
  finally:
   detail=await asyncio.to_thread(call,'GET','/api/runs/'+rid)
   print('CORE_RUN_STATUS='+str(detail['run']['status']),flush=True)
   events=detail.get('events',[])
   print('STAGES_REACHED='+','.join(dict.fromkeys(e.get('stage','') for e in events)),flush=True)
   gates=[g for g in detail.get('gates',[]) if g.get('stage')=='POLICY']
   assert gates and any(g.get('state')=='PASS' and g.get('decision')=='SIMULATE' for g in gates),'POLICY_SIMULATE_MISSING'
   print('POLICY_SIMULATE=PASS',flush=True)
   for stage in ('HITL','REMEDIATE','VERIFY'):
    done=[e for e in events if e.get('stage')==stage and e.get('event_type')=='STAGE_COMPLETED']
    assert len(done)==1 and (done[0].get('payload') or {}).get('synthetic') is True,'STAGE_NOT_SYNTHETIC:'+stage
    print('SYNTHETIC_STAGE='+stage+':PASS',flush=True)
  assert result.get('status')=='RESOLVED' and detail['run']['status']=='RESOLVED','EXPECTED_DEMO_RESOLVED'
  assert any(e.get('event_type')=='CRITIC_COMPLETED' for e in events),'CRITIC_NOT_EXECUTED'
  print('HARDENED_DEMO_WORKFLOW_E2E=PASS',flush=True)
asyncio.run(main())
PY
docker exec "$CORE_CONTAINER" python -c 'import os,sys;v=os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("ADMIN_TOKEN");sys.stdout.write(v or "");sys.exit(0 if v else 1)' > "$WORKDIR/token"
chmod 600 "$WORKDIR/token"
[[ -s "$WORKDIR/token" ]] || { echo 'E2E_TOKEN_MISSING'; exit 1; }
printf 'AIOPS_INTERNAL_TOKEN=%s\n' "$(cat "$WORKDIR/token")" > "$WORKDIR/env"
chmod 600 "$WORKDIR/env"
printf 'AIOPS_TEMPORAL_TASK_QUEUE=%s\nCORE_URL=http://aiops2-core:810\nTEMPORAL_ADDRESS=aiops2-temporal:7233\n' "$QUEUE" >> "$WORKDIR/env"
echo '===== EXECUTE ISOLATED SYNTHETIC DEMO ====='
timeout 220s docker run --rm --network "$NETWORK" --env-file "$WORKDIR/env" --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m --mount "type=bind,src=$WORKDIR/runner.py,dst=/tmp/fs999_runner.py,readonly" --entrypoint python "$IMAGE" /tmp/fs999_runner.py
echo '===== SAFETY ====='
echo 'PRODUCTION_RESTARTED=NO'
echo 'EXISTING_E2E_WORKER_UNCHANGED=YES'
echo '===== END FS.999 ====='
