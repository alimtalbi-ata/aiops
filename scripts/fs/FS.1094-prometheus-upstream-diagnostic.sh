#!/usr/bin/env bash
set -euo pipefail
IMAGE=aiops2-portal:fs1092-history-fixed-candidate
echo "FS1094_MODE=ISOLATED_PROMETHEUS_UPSTREAM_DIAGNOSTIC"
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]];then
 echo "FS1094_ERROR=UNEXPECTED_PRODUCTION_IMAGE";exit 2
fi
docker run --rm -i --network aiops2-rebuild-integration \
 -e AIOPS_INTERNAL_TOKEN=fs1094-isolated-diagnostic-only \
 -e EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 \
 -e EXPLORER_ENABLED=1 \
 --entrypoint python "$IMAGE" - <<'PY'
import os,socket,sys,urllib.request,urllib.error,urllib.parse
sys.path.insert(0,"/app")
from portal import fs1051_visual
print("FS1094_CONFIGURED_PROMETHEUS_URL="+str(fs1051_visual._PROM),flush=True)
for key in ("PROMETHEUS_URL","AIOPS_PROMETHEUS_URL","PROM_URL"):
 value=os.environ.get(key)
 print("FS1094_ENV_"+key+"="+("SET" if value else "UNSET"),flush=True)
for host in ("aiops2-rebuild-prometheus","aiops2-prometheus","prometheus"):
 try:
  addresses=sorted(set(item[4][0] for item in socket.getaddrinfo(host,9090,type=socket.SOCK_STREAM)))
  print("FS1094_DNS="+host+" ADDRS="+",".join(addresses),flush=True)
 except Exception as exc:
  print("FS1094_DNS="+host+" ERROR="+type(exc).__name__,flush=True)
for base in (str(fs1051_visual._PROM).rstrip("/"),"http://aiops2-rebuild-prometheus:9090"):
 url=base+"/api/v1/query?"+urllib.parse.urlencode({"query":"up"})
 try:
  with urllib.request.urlopen(url,timeout=5) as response:
   sample=response.read(240).decode("utf-8","replace")
   print("FS1094_HTTP_BASE="+base+" STATUS="+str(response.status)+" BODY_PREFIX="+repr(sample[:120]),flush=True)
 except Exception as exc:
  print("FS1094_HTTP_BASE="+base+" ERROR="+type(exc).__name__+" DETAIL="+str(exc)[:180],flush=True)
print("FS1094_RESULT=DIAGNOSTIC_COMPLETE",flush=True)
PY
echo "FS1094_PRODUCTION_MUTATION=NONE"
