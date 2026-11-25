"""Read-only lab context; legacy endpoints are not tenant-qualified."""
import hashlib
import http.client
import json
import re

def get(port, path):
    if type(port) is not int or not 1024 <= port <= 65535 or port in (7770,7777,7790):
        raise ValueError("invalid lab port")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        raw = response.read(65537)
        if response.status != 200 or len(raw)>65536:
            raise ValueError("unverified lab response")
        return json.loads(raw)
    finally:
        conn.close()

def context(twin_port, evidence_port, run_id, node_id):
    # Only explicitly named synthetic CI fixtures, never arbitrary tenant data.
    for value in (run_id,node_id):
        if not re.fullmatch(r"[A-Z]+-CI-[A-Z0-9-]{1,80}",value):
            raise ValueError("synthetic CI identity required")
    twin=get(twin_port,"/api/twin/impact/"+node_id)
    evidence=get(evidence_port,"/api/evidence?run_id="+run_id+"&limit=20")
    if twin.get("root")!=node_id or not isinstance(twin.get("affected"),list):
        raise ValueError("invalid impact")
    affected=[]
    for item in twin["affected"]:
        if not re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}",item["node_id"]):
            raise ValueError("non-lab topology")
        affected.append({"node_id":item["node_id"],"depth":item["depth"]})
    if not any(x["node_id"]==node_id and x["depth"]==0 for x in affected):
        raise ValueError("missing root")
    verified=[]
    for item in evidence["items"]:
        provenance=item["provenance"]
        if provenance.get("run_id")!=run_id or provenance.get("synthetic") is not True:
            raise ValueError("non-lab evidence")
        digest=hashlib.sha256(json.dumps(item["payload"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if digest!=item["payload_hash"]:
            raise ValueError("evidence hash mismatch")
        verified.append({"evidence_id":item["evidence_id"],"payload_hash":digest})
    return {"classification":"SYNTHETIC_LAB_CONTEXT","run_id":run_id,"root":node_id,
            "affected":affected,"evidence":verified,"rca":"UNKNOWN","policy":"DENY",
            "tenant_acl_qualified":False,"production_authorized":False}
