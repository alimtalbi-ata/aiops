#!/usr/bin/env bash
set -euo pipefail
IMAGE=aiops2-portal:fs1092-history-fixed-candidate
echo "FS1093_MODE=EPHEMERAL_ASGI_REAL_PROMETHEUS_NO_HTTPX"
docker image inspect "$IMAGE" >/dev/null
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]];then
 echo "FS1093_ERROR=UNEXPECTED_PRODUCTION_IMAGE";exit 2
fi
docker run --rm -i --network aiops2-rebuild-integration \
 -e AIOPS_INTERNAL_TOKEN=fs1093-isolated-asgi-test-only \
 --entrypoint python "$IMAGE" - <<'PY'
import asyncio,json,sys,urllib.parse
sys.path.insert(0,"/app")
from portal.main import app

async def request(path,params=None):
 query=urllib.parse.urlencode(params or {}).encode()
 scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},"http_version":"1.1",
        "method":"GET","scheme":"http","path":path,"raw_path":path.encode(),
        "query_string":query,"root_path":"","headers":[(b"host",b"localhost")],
        "client":("127.0.0.1",12345),"server":("localhost",80)}
 messages=[]
 sent=False
 async def receive():
  nonlocal sent
  if not sent:
   sent=True
   return {"type":"http.request","body":b"","more_body":False}
  await asyncio.sleep(3600)
  return {"type":"http.disconnect"}
 async def send(message):
  messages.append(message)
 await asyncio.wait_for(app(scope,receive,send),timeout=20)
 starts=[m for m in messages if m["type"]=="http.response.start"]
 bodies=[m.get("body",b"") for m in messages if m["type"]=="http.response.body"]
 assert len(starts)==1,(path,messages[:2])
 return starts[0]["status"],b"".join(bodies)

async def main():
 for metric in ("availability","scrape_duration"):
  for window in ("1h","6h","24h"):
   status,body=await request("/api/fs1089/prometheus/history",{"metric":metric,"window":window})
   assert status==200,(metric,window,status,body[:250])
   data=json.loads(body)
   assert data["metric"]==metric and data["window"]==window
   series=data["series"]
   assert 1<=len(series)<=30,(metric,window,len(series))
   assert all(len(s["points"])<=260 for s in series)
   assert any(s["points"] for s in series)
   print(f"FS1093_HISTORY metric={metric} window={window} STATUS=200 SERIES={len(series)} POINTS={sum(len(s['points']) for s in series)}",flush=True)
 for params in ({"metric":"process_cpu_seconds_total"},{"window":"1y"},{"metric":'up{job="foo"}'}):
  status,body=await request("/api/fs1089/prometheus/history",params)
  assert status==400,(params,status,body[:150])
  print("FS1093_INVALID_QUERY=REJECTED_400",flush=True)
 for path in ("/health","/explorer/visual","/api/fs1051/prometheus","/api/fs1051/twin"):
  status,body=await request(path)
  assert status==200,(path,status,body[:150])
  print(f"FS1093_REGRESSION={path} STATUS=200",flush=True)
 print("FS1093_RESULT=PASS",flush=True)
asyncio.run(main())
PY
echo "FS1093_PRODUCTION_MUTATION=NONE"
