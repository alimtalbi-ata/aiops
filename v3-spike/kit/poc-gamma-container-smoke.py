"""Verify the image-packaged GAMMA/HITL, including after container recreation."""
import hashlib
import json
import re
import sys
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from urllib.error import HTTPError

ORIGIN="http://127.0.0.1:18080"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=build_opener(ProxyHandler({}),NoRedirect())
def require(ok,msg):
    if not ok: raise AssertionError(msg)
def call(path,body=None,headers=None,raw=False):
    data=None if body is None else json.dumps(body).encode()
    req=Request(ORIGIN+path,data=data,headers={"Origin":ORIGIN,"Content-Type":"application/json",**(headers or {})})
    with opener.open(req,timeout=30) as response:
        payload=response.read(262145)
        require(len(payload)<=262144 and response.headers.get("Cache-Control")=="no-store","invalid response")
        return payload if raw else json.loads(payload)
def reject(path,headers,code):
    try: call(path,headers=headers)
    except HTTPError as exc: require(exc.code==code,"incorrect rejection")
    else: raise AssertionError("foreign request accepted")

def main(mode):
    require(b"<html" in call("/",raw=True).lower(),"GAMMA UI missing")
    reject("/api/v1/incident-context",{"Host":"foreign.invalid"},403)
    reject("/api/v1/incident-context",{"Origin":"http://foreign.invalid"},403)
    if mode=="initial":
        common={"kind":"metric","source":"gamma-oci-ci","resource":"NODE-CI-ROOT","severity":"warning","tenant":"synthetic-demo","synthetic":True}
        rows=[dict(common,id="gamma-oci-"+p,observation={"metric":"latency_ms","phase":p,"value":v}) for p,v in (("baseline",40),("incident",160))]
        publication=call("/api/v1/ingest/create",rows)
        require(publication==call("/api/v1/ingest/create",rows),"publication replay changed")
        rid=publication["core"]["run"]["run_id"]
        require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid),"bad run")
        decisions=[]
        for approved,expected in ((True,"SIMULATE_ONLY"),(False,"DENY")):
            pending=call("/api/v1/hitl/dynamic/request",{"run_id":rid})
            args={"run_id":rid,"request_id":pending["request_id"],"approved":approved}
            result=call("/api/v1/hitl/dynamic/decide",args)
            require(result["decision"]==expected and result["operational_decision"]=="DENY" and result["executed_on_host"] is False,"unsafe HITL")
            require(call("/api/v1/hitl/dynamic/decide",args)["decision"]=="DENY","approval replay accepted")
            decisions.append({"decision":expected,"receipt_id":result["receipt_id"],"receipt_sha256":result["receipt_sha256"]})
        report={"run_id":rid,"decisions":decisions,"evidence":sorted(publication["stored_evidence"],key=lambda r:r["evidence_id"])}
    elif mode=="replay":
        report=json.load(sys.stdin)
        rid=report["run_id"]
    else: raise ValueError("unsupported mode")
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid),"invalid run")
    path="/api/v1/incident-context/dynamic?run_id="+rid
    context=call(path)
    require(context["core"]["run"]["status"]=="CREATED" and context["production_authorized"] is False
            and context["context"]["policy"]=="DENY" and context["context"]["diagnosis"]["hypothesis"]=="LATENCY_REGRESSION_OBSERVED","invalid context")
    refs=sorted(({"evidence_id":r["evidence_id"],"payload_hash":r["payload_hash"]} for r in context["context"]["evidence"]),key=lambda r:r["evidence_id"])
    require(refs==report["evidence"],"evidence changed")
    reject(path+"&decision=execute",{},503)
    print(json.dumps({**report,"classification":"V3_PINNED_GAMMA_HITL_RUNTIME","result":"PASS","production_authorized":False},sort_keys=True))

if __name__=="__main__":
    main(sys.argv[1])
