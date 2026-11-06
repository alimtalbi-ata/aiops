#!/usr/bin/env bash
set -euo pipefail
NAME=aiops2-fs1091-diagnostic-temp
IMAGE=aiops2-portal:fs1089-history-candidate
PORT=17891
echo "FS1091_MODE=TEMPORARY_CANDIDATE_STARTUP_DIAGNOSTIC"
if docker inspect "$NAME" >/dev/null 2>&1;then echo "FS1091_ERROR=NAME_ALREADY_EXISTS";exit 2;fi
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]];then echo "FS1091_ERROR=UNEXPECTED_PRODUCTION_IMAGE";exit 2;fi
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$NAME" --restart=no --network aiops2-rebuild-integration -p "127.0.0.1:$PORT:777" \
 -e AIOPS_INTERNAL_TOKEN=fs1091-local-test-token \
 -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 "$IMAGE" >/dev/null
docker network connect aiops2-rebuild-control "$NAME"
docker network connect aiops2-rebuild-public "$NAME"
for attempt in $(seq 1 20);do
 state="$(docker inspect "$NAME" --format '{{.State.Status}}')"
 port="$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
 if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1;then
  echo "FS1091_HTTP_READY=YES ATTEMPT=$attempt"
  break
 fi
 if [[ "$attempt" == 20 ]];then echo "FS1091_HTTP_READY=NO";fi
 sleep 1
done
echo "FS1091_STATE=$(docker inspect "$NAME" --format '{{.State.Status}}')"
echo "FS1091_EXIT_CODE=$(docker inspect "$NAME" --format '{{.State.ExitCode}}')"
echo "FS1091_PORT_BINDINGS=$(docker inspect "$NAME" --format '{{json .HostConfig.PortBindings}}')"
echo "FS1091_EFFECTIVE_PORTS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
echo "FS1091_NETWORKS=$(docker inspect "$NAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}')"
echo "FS1091_LOG_TAIL_BEGIN"
docker logs --tail 35 "$NAME" 2>&1 | sed -E 's/(token|password|secret|authorization)([=: ]+)[^ ]+/\1\2[REDACTED]/Ig' | tail -35 || true
echo "FS1091_LOG_TAIL_END"
for path in /health /explorer/visual /api/fs1089/prometheus/history;do
 status="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$path" 2>/dev/null || true)"
 echo "FS1091_HTTP=$path STATUS=$status"
done
echo "FS1091_PRODUCTION_MUTATION=NONE"
echo "FS1091_RESULT=DIAGNOSTIC_COMPLETE"
