"""Read-only correlation acceptance against actual isolated GAMMA and Twin."""
import hashlib
import json
import re
import sys
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

origin=sys.argv[1]
assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) and int(origin.rsplit(":",1)[1]) not in (7770,7777,7790)
opener=build_opener(ProxyHandler({}),NoRedirect())
def call(path,data=None):
    req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),headers={"Origin":origin,"Content-Type":"application/json"})
    with opener.open(req,timeout=20) as r: return json.load(r)
p="NODE-CI-ENT-"
def row(ident,root,at,app=None,user=None):
    meta={"asset_id":p+"ASSET-PAR" if root=="NODE-CI-ROOT" else root,"occurred_at":at}
    if app: meta["application_id"]=p+app
    if user: meta["user_id"]=p+user
    return {"id":ident,"kind":"metric","source":"ci-correlation","resource":root,"tenant":"synthetic-demo","severity":"critical","synthetic":True,"enterprise":meta}
t="2026-01-01T09:00:00Z"
rows=[row("wan-1",p+"WAN",t),row("wan-2",p+"WAN","2026-01-15T09:00:00Z"),
      row("lyon-1",p+"NET-LYO","2026-01-01T09:00:01Z"),
      row("finance-1","NODE-CI-ROOT",t,"APP-PAY","USER-FIN-01"),
      row("finance-2","NODE-CI-ROOT",t,"APP-PAY","USER-FIN-02")]
def preview(records,window=120): return call("/api/v1/enterprise-correlation/preview",{"records":records,"window_seconds":window})
d=preview(rows)
assert d==preview(list(reversed(rows)))
assert d["unique"]==5 and len(d["groups"])==5
assert d["candidate_count"]==1
link=d["candidates"][0]
assert link["dependent_resource"]==p+"NET-LYO" and link["dependency_resource"]==p+"WAN" and link["gap_seconds"]==1
assert link["path"]==[{"source_id":p+"NET-LYO","target_id":p+"WAN","relation_type":"requires"}]
assert d["causality_established"] is False and d["incidents_created"] is False and d["operational_decision"]=="DENY" and d["production_authorized"] is False
assert re.fullmatch(r"[a-f0-9]{64}",d["graph_sha256"])
assert len(preview([rows[0],rows[0]])["groups"])==1
for bad in (dict(rows[0],tenant="foreign"),dict(rows[3],enterprise=dict(rows[3]["enterprise"],user_id=p+"USER-HR-01"))):
    try: preview([bad])
    except HTTPError as exc:
        assert exc.code==503 and json.load(exc)["policy"]=="DENY"
    else: raise AssertionError("invalid signal accepted")
print(json.dumps({"classification":"E15_REAL_TWIN_CORRELATION_PREVIEW","result":"PASS","groups":len(d["groups"]),"candidate_count":d["candidate_count"],"graph_sha256":d["graph_sha256"],"projection_sha256":hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest(),"production_authorized":False},sort_keys=True))
