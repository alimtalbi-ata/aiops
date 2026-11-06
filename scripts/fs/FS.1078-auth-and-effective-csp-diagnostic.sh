#!/usr/bin/env bash
set -euo pipefail
echo "FS1078_MODE=ISOLATED_AUTH_AND_CSP_DIAGNOSTIC"
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1078-placeholder -e EXPLORER_ENABLED=1 --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import asyncio,importlib,ast,pathlib
app=importlib.import_module("portal.main").app
src=pathlib.Path("/app/portal/explorer_api.py").read_text()
tree=ast.parse(src)
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ("_deny_untrusted","_check"):
  print("FS1078_AUTH_FUNCTION="+n.name+" LINES="+str(n.lineno)+"-"+str(n.end_lineno),flush=True)
  for line in src.splitlines()[n.lineno-1:n.end_lineno]:
   if any(x in line.lower() for x in ("secret","token","password","authorization","cookie")):print("FS1078_AUTH_LINE=[REDACTED]",flush=True)
   else:print("FS1078_AUTH_LINE="+line[:160],flush=True)
async def probe(label,target):
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 result={"status":None,"headers":[]}
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
 try:await asyncio.wait_for(target(scope,receive,send),timeout=8)
 except Exception as e:
  print("FS1078_"+label+"_EXCEPTION="+type(e).__name__,flush=True)
  if hasattr(e,"status_code"):print("FS1078_"+label+"_EXCEPTION_STATUS="+str(e.status_code),flush=True)
  if hasattr(e,"detail"):print("FS1078_"+label+"_EXCEPTION_DETAIL="+str(e.detail)[:100],flush=True)
 print("FS1078_"+label+"_STATUS="+str(result["status"]),flush=True)
 csps=[v for k,v in result["headers"] if k=="content-security-policy"]
 print("FS1078_"+label+"_CSP_COUNT="+str(len(csps)),flush=True)
 for c in csps:print("FS1078_"+label+"_CSP="+c[:600],flush=True)
async def main():
 await probe("ROUTER",app.router)
 await probe("FULL",app)
asyncio.run(main())
print("FS1078_RESULT=COMPLETE")
'
echo "FS1078_PRODUCTION_DEPLOY=NOT_PERFORMED"
