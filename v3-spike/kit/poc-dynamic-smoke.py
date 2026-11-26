"""Exercise real loopback GAMMA against a disposable synthetic kit; no host action."""
import json
import re
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def smoke(origin):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin):
        raise ValueError("isolated loopback origin required")
    port=int(origin.rsplit(":",1)[1])
    if not 1024<=port<=65535 or port in (7770,7777,7790):
        raise ValueError("protected or invalid port")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def call(path,body=None):
        req=Request(origin+path,data=None if body is None else json.dumps(body).encode(),
                    headers={"Origin":origin,"Content-Type":"application/json"})
        with opener.open(req,timeout=30) as response:
            raw=response.read(65537)
            if len(raw)>65536:
                raise ValueError("oversized response")
            return json.loads(raw)
    def require(value,description):
        if not value:
            raise RuntimeError(description)
    common={"kind":"metric","source":"kit-ci","resource":"NODE-CI-ROOT","severity":"critical","tenant":"synthetic-demo","synthetic":True}
    batch=[{**common,"id":"kit-baseline","observation":{"metric":"latency_ms","phase":"baseline","value":40}},
           {**common,"id":"kit-incident","observation":{"metric":"latency_ms","phase":"incident","value":160}}]
    created=call("/api/v1/ingest/create",batch)
    require(created==call("/api/v1/ingest/create",batch),"ingestion replay changed receipt")
    run=created["core"]["run"]
    rid=run["run_id"]
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid) and run["mode"]=="DEMO" and run["status"]=="CREATED","invalid run")
    path="/api/v1/incident-context/dynamic?run_id="+rid
    projection=call(path+"&decision=simulate")
    context=projection["context"]
    require(projection["core"]["run"]==run and projection["production_authorized"] is False,"wrong core binding")
    require(context["evidence"] and {e["evidence_id"]:e["payload_hash"] for e in context["evidence"]}=={e["evidence_id"]:e["payload_hash"] for e in created["stored_evidence"]},"evidence mismatch")
    require("NODE-CI-CHILD" in [n["node_id"] for n in context["affected"]],"missing topology impact")
    diagnosis=context["diagnosis"]
    require(diagnosis["hypothesis"]=="LATENCY_REGRESSION_OBSERVED" and diagnosis["preview"]["conditional_reduction_ms"]==120 and diagnosis["root_cause"]=="UNKNOWN","unexpected RCA preview")
    copilot=projection["copilot"]
    require(copilot["criticism"]["evidence_supported"] is True and copilot["criticism"]["causality_established"] is False,"invalid critic")
    require({m["evidence_id"] for m in copilot["retrieval"]["matches"]}=={e["evidence_id"] for e in context["evidence"]},"retrieval mismatch")
    sim=projection["simulation"]
    require(sim["policy_decision"]=="SIMULATE" and sim["operational_decision"]=="DENY" and sim["executed_on_host"] is False,"invalid policy")
    for approved,expected in ((True,"SIMULATE_ONLY"),(False,"DENY")):
        pending=call("/api/v1/hitl/dynamic/request",{"run_id":rid})
        require(pending["run_id"]==rid and pending["decision"]=="HUMAN_APPROVAL","invalid approval request")
        payload={"run_id":rid,"request_id":pending["request_id"],"approved":approved}
        decision=call("/api/v1/hitl/dynamic/decide",payload)
        require(decision["decision"]==expected and decision["operational_decision"]=="DENY" and decision["executed_on_host"] is False,"invalid approval decision")
        require(call("/api/v1/hitl/dynamic/decide",payload)["decision"]=="DENY","replay accepted")
    try:
        call(path+"&decision=execute")
    except HTTPError as exc:
        require(exc.code==503,"unexpected rejection status")
    else:
        raise RuntimeError("unsafe action accepted")
    after=call(path)
    require(after["core"]["run"]==run and after["context"]["evidence"]==context["evidence"],"simulation mutated state")
    print(json.dumps({"run_id":rid,"incident_id":run["incident_id"],"evidence_count":len(context["evidence"]),"result":"PASS","host_execution":False}))

if __name__=="__main__":
    smoke(sys.argv[1])
