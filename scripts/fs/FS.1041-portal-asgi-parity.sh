#!/usr/bin/env bash
# FS.1041 — offline ASGI smoke and route parity. No listening sockets or production writes.
set -euo pipefail
BASE="aiops2-portal:fs621-explorers-candidate"
CAND="aiops2-portal:fs1040-sql-guard-candidate"
echo "FS1041_MODE=ISOLATED_ASGI_NO_NETWORK"
# Use ephemeral containers to inspect routes without writing files or exporting secrets.
probe='
import asyncio, json, os
from portal.main import app
import httpx
routes=sorted(set((tuple(sorted(getattr(r,"methods",[]) or [])),getattr(r,"path","")) for r in app.routes))
print("FS1041_ROUTE_SIGNATURE="+json.dumps(routes,separators=(",",":")))
async def main():
 transport=httpx.ASGITransport(app=app,raise_app_exceptions=False)
 async with httpx.AsyncClient(transport=transport,base_url="http://localhost",timeout=4.0,follow_redirects=False) as client:
  for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog"):
   try:
    r=await client.get(path,headers={"accept":"text/html,application/json"})
    print("FS1041_HTTP=%s STATUS=%s"%(path,r.status_code))
   except Exception as exc:
    print("FS1041_HTTP=%s ERROR=%s"%(path,type(exc).__name__))
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
