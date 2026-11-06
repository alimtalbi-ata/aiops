#!/usr/bin/env bash
set -euo pipefail
echo "FS1075_MODE=ISOLATED_503_AND_CSP_DIAG"
docker run --rm --network none -e AIOPS_INTERNAL_TOKEN=fs1075-isolated-placeholder-token --entrypoint python aiops2-portal:fs1073-csp-candidate -c '
import ast, pathlib, importlib, inspect, asyncio
from fastapi import Request
m=importlib.import_module("portal.main")
print("FS1075_MIDDLEWARE_COUNT="+str(len(m.app.user_middleware)))
for mw in m.app.user_middleware:
 print("FS1075_MIDDLEWARE="+str(mw.cls.__module__)+"."+str(mw.cls.__name__))
p=pathlib.Path("/app/portal/main.py")
tree=ast.parse(p.read_text())
for node in ast.walk(tree):
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(x in node.name.lower() for x in ("middleware","ready","health","guard")):
  print("FS1075_FUNCTION="+node.name+" LINES="+str(node.lineno)+"-"+str(node.end_lineno))
 if isinstance(node,ast.Call):
  f=node.func
  if isinstance(f,ast.Attribute) and f.attr in ("add_middleware","middleware"):
   print("FS1075_MIDDLEWARE_REGISTRATION_LINE="+str(node.lineno))
v=importlib.import_module("portal.fs1051_visual")
print("FS1075_ROUTE="+str(inspect.signature(v.visual)))
async def probe():
 scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/explorer/visual","raw_path":b"/explorer/visual","query_string":b"","root_path":"","headers":[(b"host",b"127.0.0.1:7777")],"client":("127.0.0.1",40000),"server":("127.0.0.1",7777)}
 for label,app in (("FULL",m.app),("ROUTER",m.app.router)):
  result={"status":None,"headers":[],"body":bytearray()}
  async def receive():return {"type":"http.request","body":b"","more_body":False}
  async def send(msg):
   if msg["type"]=="http.response.start":
    result["status"]=msg["status"]
    result["headers"]=[(k.decode("latin1").lower(),v.decode("latin1")) for k,v in msg["headers"]]
   if msg["type"]=="http.response.body":result["body"].extend(msg.get("body",b""))
  try:await asyncio.wait_for(app(scope,receive,send),timeout=8)
  except Exception as exc:print("FS1075_"+label+"_EXCEPTION="+type(exc).__name__)
  print("FS1075_"+label+"_STATUS="+str(result["status"]))
  print("FS1075_"+label+"_CSP="+str([v for k,v in result["headers"] if k=="content-security-policy"])[:700])
  print("FS1075_"+label+"_BODY_LENGTH="+str(len(result["body"])))
asyncio.run(probe())
print("FS1075_RESULT=COMPLETE")
'
echo "FS1075_PRODUCTION_DEPLOY=NOT_PERFORMED"
