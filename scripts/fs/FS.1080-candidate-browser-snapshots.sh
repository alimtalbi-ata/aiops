#!/usr/bin/env bash
set -euo pipefail
echo "FS1080_MODE=TEMPORARY_CANDIDATE_REAL_BROWSER"
NAME=aiops2-fs1080-csp-browser-temp
PORT=17877
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
if docker container inspect "$NAME" >/dev/null 2>&1; then echo "FS1080_ERROR=TEMP_NAME_ALREADY_EXISTS";exit 1;fi
trap cleanup EXIT
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker network inspect aiops2-rebuild-public >/dev/null
docker network inspect aiops2-rebuild-control >/dev/null
docker network inspect aiops2-rebuild-integration >/dev/null
docker run -d --name "$NAME" --restart no --network aiops2-rebuild-public -p "127.0.0.1:${PORT}:777" -e AIOPS_INTERNAL_TOKEN=fs1080-nonprod-placeholder -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 aiops2-portal:fs1073-csp-candidate >/dev/null
docker network connect aiops2-rebuild-control "$NAME"
docker network connect aiops2-rebuild-integration "$NAME"
READY=NO
for i in $(seq 1 35); do
 if curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/explorer/visual" -o /dev/null; then READY=YES;break;fi
 sleep 1
done
echo "FS1080_HTTP_READY=$READY"
if [ "$READY" != YES ]; then docker logs --tail 25 "$NAME" 2>&1 | sed -E 's/(token|secret|password)=([^ ]+)/\\1=[REDACTED]/Ig';exit 1;fi
/home/aiops/.local/share/aiops-playwright-venv/bin/python "$(dirname "$0")/fs1080_browser_candidate.py"
echo "FS1080_PRODUCTION_DEPLOY=NOT_PERFORMED"
