"""Mission Control static entry and allowlisted technical health projection."""
import json
import urllib.parse
import urllib.request
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()
ROOT = Path(__file__).with_name("mission_dist")
PROM = "http://aiops2-rebuild-prometheus:9090/api/v1/query"
JOBS = ("aiops2-core","aiops2-worker","aiops2-twin","aiops2-policy","aiops2-evidence","aiops2-portal")
@router.get("/api/mission-control/snapshot")
def snapshot():
    services = [dict(name=j,up=None) for j in JOBS]
    at = None
    try:
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        expr='min by(job) (up{job=~"'+ "|".join(JOBS)+'"})'
        with op.open(PROM+"?"+urllib.parse.urlencode({"query":expr}),timeout=3) as r:
            rows=json.load(r)["data"]["result"]
        values={row["metric"]["job"]:row["value"] for row in rows}
        for s in services:
            v=values.get(s["name"])
            if v and v[1] in ("0","1"):
                s["up"]=int(v[1])
                at=float(v[0])
    except Exception:
        pass
    metrics=[dict(label="Services supervisés",value=len(JOBS),at=at),
             dict(label="Services UP",value=sum(s["up"]==1 for s in services) if at is not None else None,at=at),
             dict(label="Services DOWN",value=sum(s["up"]==0 for s in services) if at is not None else None,at=at),
             dict(label="État inconnu",value=sum(s["up"] is None for s in services),at=at)]
    return JSONResponse(dict(metrics=metrics,services=services),headers={"Cache-Control":"no-store"})
@router.get("/gamma",include_in_schema=False)
def gamma():
    return FileResponse(ROOT/"index.html",headers={"Cache-Control":"no-store","Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"})
