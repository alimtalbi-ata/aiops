#!/usr/bin/env bash
# FS.1043 — offline ASGI HTTP parity with explicit loopback CIDR and denied-client check.
set -euo pipefail
echo "FS1043_MODE=OFFLINE_ASGI"
probe='
import asyncio,json
from portal.main import app
routes=sorted(set((tuple(sorted(getattr(r,"methods",[]) or [])),getattr(r,"path","")) for r in app.routes))
print("FS1043_ROUTE_SIGNATURE="+json.dumps(routes,separators=(",",":")))
async def check(path,client_ip):
 status=[None]
 received=[False]
 async def receive():
  if not received[0]:
   received[0]=True
   return {"type":"http.request","body":b"","more_body":False}
  await asyncio.sleep(3600)
 async def send(msg):
  if msg["type"]=="http.response.start": status[0]=msg["status"]
 scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},
  "http_version":"1.1","method":"GET","scheme":"http","path":path,
  "raw_path":path.encode(),"query_string":b"","root_path":"",
  "headers":[(b"host",b"localhost"),(b"accept",b"text/html,application/json")],
  "client":(client_ip,12345),"server":("localhost",80)}
 try:
  await asyncio.wait_for(app(scope,receive,send),timeout=4)
  print("FS1043_HTTP=%s CLIENT=%s STATUS=%s"%(path,client_ip,status[0]))
 except Exception as exc:
  print("FS1043_HTTP=%s CLIENT=%s ERROR=%s"%(path,client_ip,type(exc).__name__))
async def main():
 for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog"):
  await check(path,"127.0.0.1")
 await check("/api/explorer/catalog","192.0.2.1")
asyncio.run(main())
'
run_probe() {
 docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env AIOPS_INTERNAL_TOKEN=fs1043-offline-dummy-token \
  --env EXPLORER_ENABLED=1 \
  --env EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 \
  --entrypoint python "$1" -c "$probe"
}
BASE="$(run_probe aiops2-portal:fs621-explorers-candidate)"
CAND="$(run_probe aiops2-portal:fs1040-sql-guard-candidate)"
BASE_SIG="$(printf '%s\n' "$BASE" | sed -n 's/^FS1043_ROUTE_SIGNATURE=//p')"
CAND_SIG="$(printf '%s\n' "$CAND" | sed -n 's/^FS1043_ROUTE_SIGNATURE=//p')"
if [[ -z "$BASE_SIG" || "$BASE_SIG" != "$CAND_SIG" ]]; then echo "FS1043_ROUTE_PARITY=FAIL"; exit 1; fi
echo "FS1043_ROUTE_PARITY=PASS"
echo "===== BASE ====="
printf '%s\n' "$BASE" | grep '^FS1043_HTTP='
echo "===== CANDIDATE ====="
printf '%s\n' "$CAND" | grep '^FS1043_HTTP='
B="$(printf '%s\n' "$BASE" | grep '^FS1043_HTTP=' || true)"
C="$(printf '%s\n' "$CAND" | grep '^FS1043_HTTP=' || true)"
if [[ "$B" != "$C" ]]; then echo "FS1043_HTTP_PARITY=FAIL"; exit 1; fi
echo "FS1043_HTTP_PARITY=PASS"
if printf '%s\n' "$C" | grep -Eq 'ERROR=|STATUS=5[0-9][0-9]|STATUS=None'; then echo "FS1043_HTTP_HEALTH=FAIL"; exit 1; fi
if ! printf '%s\n' "$C" | grep -Eq '^FS1043_HTTP=/api/explorer/catalog CLIENT=192\.0\.2\.1 STATUS=(403|503)$'; then
 echo "FS1043_UNTRUSTED_CLIENT=FAIL"; exit 1
fi
echo "FS1043_UNTRUSTED_CLIENT=PASS"
echo "FS1043_CANDIDATE=PASS"
