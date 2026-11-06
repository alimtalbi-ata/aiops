#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.969 | FINAL READ-ONLY AUDIT ====='
CONTAINER=aiops2-rebuild-worker
SOURCE=/home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py
EXPECTED=ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda
RID=RUN-8FD05627DCB0DE1A
echo '===== 1. CODE INTEGRITY ====='
echo "$EXPECTED  $SOURCE" | sha256sum -c -
docker exec "$CONTAINER" sha256sum /app/worker/main.py
echo '===== 2. WORKER STATUS ====='
docker inspect "$CONTAINER" --format 'RUNNING={{.State.Running}} RESTART_COUNT={{.RestartCount}} STARTED_AT={{.State.StartedAt}}'
echo '===== 3. CORE AND TEMPORAL ====='
docker exec -i "$CONTAINER" python - <<'PY'
import os,requests,asyncio
from temporalio.client import Client
rid='RUN-8FD05627DCB0DE1A'
core=os.getenv('CORE_URL','http://aiops2-core:810').rstrip('/')
r=requests.get(core+'/api/runs/'+rid,timeout=8)
print('CORE_HTTP='+str(r.status_code))
r.raise_for_status()
obj=r.json()
print('CORE_RUN_STATUS='+str(obj.get('run',{}).get('status')))
async def main():
 c=await Client.connect('aiops2-rebuild-temporal:7233',namespace='default')
 count=0
 async for item in c.list_workflows('WorkflowId="'+rid+'"'):
  count+=1
  print('TEMPORAL_WORKFLOW_ID='+str(item.id))
  print('TEMPORAL_RUN_ID='+str(item.run_id))
  print('TEMPORAL_STATUS='+str(item.status))
  print('TEMPORAL_START_TIME='+str(item.start_time))
  print('TEMPORAL_CLOSE_TIME='+str(item.close_time))
 print('TEMPORAL_MATCHING_EXECUTIONS='+str(count))
asyncio.run(main())
print('HTTP_METHODS=GET_ONLY')
print('WORKFLOWS_STARTED=NO')
PY
echo '===== 4. RECENT WORKER LOGS ====='
docker logs --since 30m --tail 100 "$CONTAINER" 2>&1 |
 grep -Ei 'error|exception|traceback|/api/execution/start|startup|503|409|404' |
 sed -E -e 's/(Bearer )[A-Za-z0-9._~+\/=:-]+/\1[REDACTED]/Ig' || true
echo 'FILES_MODIFIED=NO'
echo '===== END FS.969 ====='
