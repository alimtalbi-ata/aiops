#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.968 | BLOCKED RUN HTTP 409 ====='
EXPECTED=ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda
TARGET=/home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py
echo "$EXPECTED  $TARGET" | sha256sum -c -
docker exec -i aiops2-rebuild-worker python - <<'PY'
import os,requests
rid='RUN-8FD05627DCB0DE1A'
core=os.getenv('CORE_URL','http://aiops2-core:810').rstrip('/')
token=os.environ.get('AIOPS_ADMIN_TOKEN')
if not token: raise SystemExit('REFUSED: missing admin token')
r=requests.get(core+'/api/runs/'+rid,timeout=8)
r.raise_for_status()
body=r.json()
status=body.get('run',{}).get('status')
print('CORE_RUN_STATUS='+str(status))
if status!='BLOCKED':
 raise SystemExit('REFUSED: run is not BLOCKED')
print('PRECONDITION_BLOCKED=PASS')
r=requests.post('http://127.0.0.1:815/api/execution/start',
 headers={'Authorization':'Bearer '+token},
 json={'run_id':rid},timeout=15)
print('WORKER_HTTP='+str(r.status_code))
if r.status_code!=409:
 raise SystemExit('FAIL: expected 409; inspect Temporal before retry')
print('BLOCKED_RUN_GUARD=PASS')
PY
echo '===== END FS.968 ====='
