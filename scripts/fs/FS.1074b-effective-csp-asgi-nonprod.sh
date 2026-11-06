#!/usr/bin/env bash
set -euo pipefail
echo "FS1074B_MODE=NONPROD_EFFECTIVE_CSP_ASGI"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1074b-isolated-placeholder-token --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import asyncio,importlib
async def run():
 app=importlib.import_module("portal.main").app
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 result={"headers":[]}
 async def receive():return {"type":"http.request","body":b"","more_body":False}
 async def send(message):
  if message["type"]=="http.response.start":
   result["status"]=message["status"]
   result["headers"]=[(k.decode("latin1").lower(),v.decode("latin1")) for k,v in message["headers"]]
 await asyncio.wait_for(app(scope,receive,send),timeout=12)
 print("FS1074B_HTTP_STATUS="+str(result.get("status")),flush=True)
 csps=[v for k,v in result["headers"] if k=="content-security-policy"]
 print("FS1074B_CSP_HEADER_COUNT="+str(len(csps)),flush=True)
 for csp in csps:print("FS1074B_EFFECTIVE_CSP="+csp[:700],flush=True)
 assert result.get("status")==200,"ASGI status not 200"
 assert len(csps)==1,"expected exactly one CSP header"
 csp=csps[0]
 assert all(k in csp for k in ("script-src","style-src","connect-src","default-src")),"CSP directives missing"
 assert csp.count("sha256-")>=2,"CSP hashes missing"
 assert "unsafe-inline" not in csp,"unsafe-inline prohibited"
 print("FS1074B_CSP_HEADERS=PASS",flush=True)
asyncio.run(run())
'
echo "FS1074B_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1074B_RESULT=PASS"
