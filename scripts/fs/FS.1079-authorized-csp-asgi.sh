#!/usr/bin/env bash
set -euo pipefail
echo "FS1079_MODE=NONPROD_AUTHORIZED_EFFECTIVE_CSP"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1079-placeholder -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import asyncio,importlib
app=importlib.import_module("portal.main").app
async def probe(label,target):
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 result={"status":None,"headers":[],"body":bytearray()}
 sent=False
 async def receive():
  nonlocal sent
  if not sent:
   sent=True
   return {"type":"http.request","body":b"","more_body":False}
  await asyncio.sleep(3600)
 async def send(msg):
  if msg["type"]=="http.response.start":
   result["status"]=msg["status"]
   result["headers"]=[(k.decode("latin1").lower(),v.decode("latin1")) for k,v in msg["headers"]]
  elif msg["type"]=="http.response.body":result["body"].extend(msg.get("body",b""))
 try:await asyncio.wait_for(target(scope,receive,send),timeout=10)
 except Exception as e:
  print("FS1079_"+label+"_EXCEPTION="+type(e).__name__,flush=True)
  if hasattr(e,"status_code"):print("FS1079_"+label+"_EXCEPTION_STATUS="+str(e.status_code),flush=True)
 csps=[v for k,v in result["headers"] if k=="content-security-policy"]
 print("FS1079_"+label+"_STATUS="+str(result["status"]),flush=True)
 print("FS1079_"+label+"_CSP_COUNT="+str(len(csps)),flush=True)
 for csp in csps:print("FS1079_"+label+"_CSP="+csp[:700],flush=True)
 print("FS1079_"+label+"_BODY_BYTES="+str(len(result["body"])),flush=True)
 return result,csps
async def main():
 r,rc=await probe("ROUTER",app.router)
 f,fc=await probe("FULL",app)
 assert r["status"]==200 and f["status"]==200,"authorized response not 200"
 assert len(rc)==1 and len(fc)==1,"expected one CSP per response"
 assert all(c.count("sha256-")>=2 and "unsafe-inline" not in c for c in rc+fc),"CSP hashes lost or unsafe-inline"
 assert b"Observabilit" in f["body"],"dashboard body absent"
 print("FS1079_EFFECTIVE_CSP=PASS",flush=True)
asyncio.run(main())
'
echo "FS1079_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1079_RESULT=PASS"
