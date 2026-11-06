#!/usr/bin/env bash
set -euo pipefail
echo "FS1077_MODE=NONPROD_ENABLED_EXPLORER_EFFECTIVE_CSP"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1077-isolated-placeholder-token -e EXPLORER_ENABLED=1 --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import asyncio,importlib
async def main():
 app=importlib.import_module("portal.main").app
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 for label,target in (("ROUTER",app.router),("FULL",app)):
  result={"headers":[],"status":None,"body":bytearray()}
  sent=False
  async def receive():
   nonlocal sent
   if not sent:
    sent=True
    return {"type":"http.request","body":b"","more_body":False}
   await asyncio.sleep(3600)
  async def send(message):
   if message["type"]=="http.response.start":
    result["status"]=message["status"]
    result["headers"]=[(k.decode("latin1").lower(),v.decode("latin1")) for k,v in message["headers"]]
   if message["type"]=="http.response.body":result["body"].extend(message.get("body",b""))
  try:await asyncio.wait_for(target(scope,receive,send),timeout=10)
  except Exception as e:print("FS1077_"+label+"_ERROR="+type(e).__name__,flush=True)
  csps=[v for k,v in result["headers"] if k=="content-security-policy"]
  print("FS1077_"+label+"_STATUS="+str(result["status"]),flush=True)
  print("FS1077_"+label+"_CSP_COUNT="+str(len(csps)),flush=True)
  for csp in csps:print("FS1077_"+label+"_CSP="+csp[:700],flush=True)
  print("FS1077_"+label+"_BODY_BYTES="+str(len(result["body"])),flush=True)
  assert result["status"]==200,label+" response not 200"
  assert len(csps)==1,label+" CSP count not one"
  assert csps[0].count("sha256-")>=2,label+" CSP hashes missing"
  assert "unsafe-inline" not in csps[0],label+" unsafe-inline"
 print("FS1077_EFFECTIVE_CSP=PASS",flush=True)
asyncio.run(main())
'
echo "FS1077_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1077_RESULT=PASS"
