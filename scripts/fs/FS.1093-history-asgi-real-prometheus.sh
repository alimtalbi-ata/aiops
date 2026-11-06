#!/usr/bin/env bash
set -euo pipefail
IMAGE=aiops2-portal:fs1092-history-fixed-candidate
echo "FS1093_MODE=EPHEMERAL_ASGI_REAL_PROMETHEUS"
docker image inspect "$IMAGE" >/dev/null
docker inspect aiops2-rebuild-portal >/dev/null
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]];then
 echo "FS1093_ERROR=UNEXPECTED_PRODUCTION_IMAGE";exit 2
fi
docker run --rm --network aiops2-rebuild-integration \
 -e AIOPS_INTERNAL_TOKEN=fs1093-isolated-asgi-test-only \
 --entrypoint python "$IMAGE" - <<'PY'
import asyncio,json,sys
sys.path.insert(0,"/app")
from portal.main import app
import httpx
async def main():
 transport=httpx.ASGITransport(app=app)
 async with httpx.AsyncClient(transport=transport,base_url="http://localhost",timeout=20) as client:
  for metric in ("availability","scrape_duration"):
   for window in ("1h","6h","24h"):
    response=await client.get("/api/fs1089/prometheus/history",params={"metric":metric,"window":window})
    assert response.status_code==200,(metric,window,response.status_code,response.text[:250])
    data=response.json()
    assert data["metric"]==metric and data["window"]==window
    series=data["series"]
    assert 1<=len(series)<=30,(metric,window,len(series))
    assert all(len(s["points"])<=260 for s in series)
    assert any(s["points"] for s in series)
    print(f"FS1093_HISTORY metric={metric} window={window} STATUS=200 SERIES={len(series)} POINTS={sum(len(s['points']) for s in series)}",flush=True)
  for params in ({"metric":"process_cpu_seconds_total"},{"window":"1y"},{"metric":'up{job="foo"}'}):
   response=await client.get("/api/fs1089/prometheus/history",params=params)
   assert response.status_code==400,(params,response.status_code,response.text[:150])
   print("FS1093_INVALID_QUERY=REJECTED_400",flush=True)
  for path in ("/health","/explorer/visual","/api/fs1051/prometheus","/api/fs1051/twin"):
   response=await client.get(path)
   assert response.status_code==200,(path,response.status_code,response.text[:150])
   print(f"FS1093_REGRESSION={path} STATUS=200",flush=True)
  print("FS1093_RESULT=PASS",flush=True)
asyncio.run(main())
PY
echo "FS1093_PRODUCTION_MUTATION=NONE"
