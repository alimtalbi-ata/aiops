#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.967 | POST-DEPLOYMENT 404 VALIDATION ====='
EXPECTED=ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda
TARGET=/home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py
echo "$EXPECTED  $TARGET" | sha256sum -c -
docker exec -i aiops2-rebuild-worker python - <<'PY'
import os,requests
from pathlib import Path
token=os.environ.get('AIOPS_ADMIN_TOKEN')
if not token:
 raise SystemExit('TEST_NOT_RUN: AIOPS_ADMIN_TOKEN missing')
s=Path('/app/worker/main.py').read_text()
assert "raise HTTPException(404, 'run not found')" in s
base='http://127.0.0.1:815'
health=requests.get(base+'/health',timeout=8)
print('HEALTH_HTTP='+str(health.status_code))
health.raise_for_status()
r=requests.post(base+'/api/execution/start',
 headers={'Authorization':'Bearer '+token},
 json={'run_id':'RUN-FS967-DOES-NOT-EXIST'},timeout=15)
print('MISSING_RUN_HTTP='+str(r.status_code))
if r.status_code!=404:
 raise SystemExit('FAIL: expected HTTP 404; investigate before further tests')
print('HTTP_404_GUARD=PASS')
print('BLOCKED_RUN_POST_TESTED=NO')
PY
echo '===== END FS.967 ====='
