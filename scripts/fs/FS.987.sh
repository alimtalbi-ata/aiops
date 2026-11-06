#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.987 | E2E GUARDED WORKER GAP ASSESSMENT ====='
GUARDED=aiops2-worker:fs001d-guard-validated-20261106
E2E=aiops2-e2e-v1-aiops2-worker-1
PROD=aiops2-rebuild-worker
docker image inspect "$GUARDED" >/dev/null
echo '===== EFFECTIVE SOURCE HASHES ====='
GUARDED_SHA="$(docker run --rm --network none --entrypoint python "$GUARDED" -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
E2E_SHA="$(docker exec "$E2E" python -c 'import hashlib;print(hashlib.sha256(open("/app/worker/main.py","rb").read()).hexdigest())')"
echo "GUARDED_SHA256=$GUARDED_SHA"
echo "E2E_ACTIVE_SHA256=$E2E_SHA"
if [[ "$GUARDED_SHA" == "$E2E_SHA" ]]; then echo 'E2E_GUARDED_PARITY=PASS'; else echo 'E2E_GUARDED_PARITY=FAIL'; fi
echo '===== WORKER PROCESS AND NETWORK ====='
docker inspect "$E2E" --format 'E2E_RUNNING={{.State.Running}} E2E_IMAGE={{.Config.Image}} E2E_COMMAND={{json .Config.Cmd}}'
docker inspect "$PROD" --format 'PROD_RUNNING={{.State.Running}} PROD_IMAGE={{.Config.Image}}'
echo '===== PORTAL E2E DISCOVERY ====='
docker ps --format '{{.Names}}' | grep '^aiops2-e2e-v1-' | sort
if docker ps --format '{{.Names}}' | grep -Eq '^aiops2-e2e-v1-.*portal'; then echo 'E2E_PORTAL_CONTAINER=FOUND'; else echo 'E2E_PORTAL_CONTAINER=NOT_FOUND'; fi
echo '===== CANDIDATE WORKFLOW MODULE ====='
docker run --rm --network none --env AIOPS_INTERNAL_TOKEN=fs987-isolated-token --entrypoint python "$GUARDED" -c 'import worker.workflow as w; print("INCIDENT_WORKFLOW_IMPORT=PASS"); print("STAGES="+",".join(w.STAGES))'
echo '===== NO MUTATIONS ====='
echo 'E2E_CONTAINERS_REPLACED=0'
echo 'BUSINESS_WORKFLOWS_STARTED=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.987 ====='
