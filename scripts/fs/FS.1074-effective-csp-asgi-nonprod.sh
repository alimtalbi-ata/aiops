#!/usr/bin/env bash
set -euo pipefail
echo "FS1074_MODE=NONPROD_EFFECTIVE_CSP_ASGI"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker run --rm --network none --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import asyncio,importlib
from pathlib import Path
from urllib.parse import quote
async def run():
 m=importlib.import_module("portal.main")
 app=m.app
 paths=[getattr(r,"path",None) for r in app.router.routes]
 assert "/explorer/visual" in paths,"visual route missing"
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 started={}
 async def receive():return {"type":"http.request","body":b"","more_body":False}
 async def send(message):
  if message["type"]=="http.response.start":
   started["status"]=message["status"]
   started["headers"]={k.decode("latin1").lower():v.decode("latin1") for k,v in message["headers"]}
 await asyncio.wait_for(app(scope,receive,send),timeout=12)
 print("FS1074_HTTP_STATUS="+str(started.get("status")),flush=True)
 h=started.get("headers",{})
 csp=h.get("content-security-policy","")
 print("FS1074_EFFECTIVE_CSP="+csp[:700],flush=True)
 print("FS1074_CSP_COUNT="+str(sum(k=="content-security-policy" for k in h)),flush=True)
 assert started.get("status")==200,"ASGI status not 200"
 assert "script-src" in csp and "style-src" in csp and "connect-src" in csp,"CSP directives missing"
 assert csp.count("sha256-")>=2,"CSP hashes missing"
 assert "unsafe-inline" not in csp,"unsafe-inline prohibited"
 print("FS1074_CSP_HEADERS=PASS",flush=True)
asyncio.run(run())
'
echo "FS1074_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1074_RESULT=PASS"
