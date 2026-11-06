#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
IMAGE=aiops2-portal:fs1097-history-chart-candidate
echo "FS1097_MODE=NONPRODUCTION_HISTORY_CHART_BUILD_AND_ASGI_TEST"
docker image inspect aiops2-portal:fs1092-history-fixed-candidate >/dev/null
docker build -f "$ROOT/scripts/fs/Dockerfile.fs1097" -t "$IMAGE" "$ROOT"
docker run --rm -e AIOPS_INTERNAL_TOKEN=fs1097-import-only-test --entrypoint python "$IMAGE" - <<'PY'
import ast,base64,hashlib,pathlib,re,sys
sys.path.insert(0,"/app")
from portal.main import app
from portal.fs1051_visual import router
paths=[r.path for r in app.routes]
assert paths.count("/api/fs1089/prometheus/history")==1
assert paths.count("/explorer/visual")==1
assert len(router.routes)==3
html=pathlib.Path("/app/portal/fs1051_visual.html").read_text()
api=pathlib.Path("/app/portal/fs1051_visual.py").read_text()
style=re.search(r"<style>(.*?)</style>",html,re.S).group(1)
script=re.search(r"<script>(.*?)</script>",html,re.S).group(1)
def h(s):return "'sha256-"+base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()+"'"
assert "script-src "+h(script)+"; style-src "+h(style) in api
for token in ('history-chart','history-metric','history-window','history-refresh','/api/fs1089/prometheus/history'):
 assert token in html
print("FS1097_IMPORT=PASS")
print("FS1097_ROUTE_INVARIANTS=PASS")
print("FS1097_CSP_HASHES=PASS")
print("FS1097_HISTORY_UI=PASS")
PY
docker run --rm -i --network aiops2-rebuild-control \
 -e AIOPS_INTERNAL_TOKEN=fs1097-isolated-asgi-test-only \
 -e EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 -e EXPLORER_ENABLED=1 \
 --entrypoint python "$IMAGE" - <<'PY'
import asyncio,json,sys,urllib.parse
sys.path.insert(0,"/app")
from portal.main import app
async def request(path,params=None):
 query=urllib.parse.urlencode(params or {}).encode()
 scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},"http_version":"1.1","method":"GET","scheme":"http","path":path,"raw_path":path.encode(),"query_string":query,"root_path":"","headers":[(b"host",b"localhost")],"client":("127.0.0.1",12345),"server":("localhost",80)}
 messages=[];sent=False
 async def receive():
  nonlocal sent
  if not sent:sent=True;return {"type":"http.request","body":b"","more_body":False}
  await asyncio.sleep(3600)
 async def send(m):messages.append(m)
 await asyncio.wait_for(app(scope,receive,send),timeout=20)
 start=next(m for m in messages if m["type"]=="http.response.start")
 body=b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
 return start["status"],dict(start["headers"]),body
async def main():
 status,headers,body=await request("/explorer/visual")
 assert status==200,status
 csp=dict((k.decode(),v.decode()) for k,v in headers.items()).get("content-security-policy","")
 assert "script-src 'sha256-" in csp and "style-src 'sha256-" in csp
 print("FS1097_ASGI_VISUAL=200 CSP=PASS",flush=True)
 for metric in ("availability","scrape_duration"):
  status,_,body=await request("/api/fs1089/prometheus/history",{"metric":metric,"window":"1h"})
  assert status==200,(metric,status,body[:180])
  data=json.loads(body);assert data["series"] and any(s["points"] for s in data["series"])
  print(f"FS1097_ASGI_HISTORY metric={metric} STATUS=200 SERIES={len(data['series'])} POINTS={sum(len(s['points']) for s in data['series'])}",flush=True)
 print("FS1097_RESULT=PASS",flush=True)
asyncio.run(main())
PY
echo "FS1097_IMAGE=$IMAGE"
echo "FS1097_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1097_PRODUCTION_MUTATION=NONE"
