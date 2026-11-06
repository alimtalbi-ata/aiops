#!/usr/bin/env bash
# FS.1041 — offline ASGI smoke and route parity. No listening sockets or production writes.
set -euo pipefail
BASE="aiops2-portal:fs621-explorers-candidate"
CAND="aiops2-portal:fs1040-sql-guard-candidate"
echo "FS1041_MODE=ISOLATED_ASGI_NO_NETWORK"
# Use ephemeral containers to inspect routes without writing files or exporting secrets.
probe='
import asyncio, json
from portal.main import app
routes=sorted(set((tuple(sorted(getattr(r,"methods",[]) or [])),getattr(r,"path","")) for r in app.routes))
print("FS1041_ROUTE_SIGNATURE="+json.dumps(routes,separators=(",",":")))
async def check(path):
 status=[None]
 sent=[False]
 async def receive():
  if not sent[0]:
   sent[0]=True
   return {"type":"http.request","body":b"","more_body":False}
  await asyncio.sleep(3600)
 async def send(message):
  if message["type"]=="http.response.start":
   status[0]=message["status"]
 scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},
  "http_version":"1.1","method":"GET","scheme":"http","path":path,
  "raw_path":path.encode(),"query_string":b"","root_path":"",
  "headers":[(b"host",b"localhost"),(b"accept",b"text/html,application/json")],
  "client":("127.0.0.1",12345),"server":("localhost",80)}
 try:
  await asyncio.wait_for(app(scope,receive,send),timeout=4)
  print("FS1041_HTTP=%s STATUS=%s"%(path,status[0]))
 except Exception as exc:
  print("FS1041_HTTP=%s ERROR=%s"%(path,type(exc).__name__))
async def main():
 for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog"):
  await check(path)
asyncio.run(main())
'
# Host captures only route signature and HTTP status, not response bodies.
run_probe() {
  docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --env AIOPS_INTERNAL_TOKEN=fs1041-offline-dummy-token \
    --env EXPLORER_ENABLED=1 \
    --entrypoint python "$1" -c "$probe"
}
BASE_OUT="$(run_probe "$BASE")"
CAND_OUT="$(run_probe "$CAND")"
BASE_SIG="$(printf '%s\n' "$BASE_OUT" | sed -n 's/^FS1041_ROUTE_SIGNATURE=//p')"
CAND_SIG="$(printf '%s\n' "$CAND_OUT" | sed -n 's/^FS1041_ROUTE_SIGNATURE=//p')"
if [[ -z "$BASE_SIG" || -z "$CAND_SIG" ]]; then
  echo "FS1041_ROUTE_PARITY=FAIL_MISSING_SIGNATURE"
  exit 1
fi
if [[ "$BASE_SIG" != "$CAND_SIG" ]]; then
  echo "FS1041_ROUTE_PARITY=FAIL"
  exit 1
fi
echo "FS1041_ROUTE_PARITY=PASS"
echo "===== BASE HTTP ====="
printf '%s\n' "$BASE_OUT" | grep '^FS1041_HTTP='
echo "===== CANDIDATE HTTP ====="
printf '%s\n' "$CAND_OUT" | grep '^FS1041_HTTP='
BASE_HTTP="$(printf '%s\n' "$BASE_OUT" | grep '^FS1041_HTTP=' || true)"
CAND_HTTP="$(printf '%s\n' "$CAND_OUT" | grep '^FS1041_HTTP=' || true)"
if [[ "$BASE_HTTP" != "$CAND_HTTP" ]]; then
  echo "FS1041_HTTP_PARITY=FAIL"
  exit 1
fi
if [[ "$CAND_HTTP" == *"ERROR="* || "$CAND_HTTP" == *"STATUS=500"* || "$CAND_HTTP" == *"STATUS=502"* || "$CAND_HTTP" == *"STATUS=503"* ]]; then
  echo "FS1041_HTTP_HEALTH=FAIL"
  exit 1
fi
echo "FS1041_HTTP_PARITY=PASS"
echo "FS1041_CANDIDATE=PASS"
