"""Read the actual E17 receipt and independent Verify through GAMMA's HTTP API."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from urllib.error import HTTPError

origin,root=sys.argv[1:]
assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin)
assert int(origin.rsplit(":",1)[1]) not in (7770,7777,7790)
root=Path(root)
assert root==Path("/tmp/aiops-v3-rootless-ci")
report=json.loads((root/"temporal-e17.json").read_text())
worker=json.loads((root/"temporal-e17-worker-replay.json").read_text())
rid=report["workflow_id"]
comparison=report["verification"]["comparison_run_id"]
assert all(re.fullmatch(r"RUN-[A-F0-9]{16}",v) for v in (rid,comparison))
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=build_opener(ProxyHandler({}),NoRedirect())
def path(original,after):
    return "/api/v1/e17/recovery?"+urlencode({"original_run_id":original,"comparison_run_id":after})
def get(route,headers=None):
    with opener.open(Request(origin+route,headers=headers or {}),timeout=30) as r:
        raw=r.read(65537)
        assert len(raw)<=65536 and r.headers["Cache-Control"]=="no-store"
        return json.loads(raw)
result=get(path(rid,comparison))
assert result=={"classification":"SYNTHETIC_GAMMA_E17_VERIFIED_READBACK",
                "worker":worker,"verification":report["verification"],
                "operational_decision":"DENY","production_authorized":False,
                "tenant_acl_qualified":False,"core_business_stages_qualified":False}
for route,headers in ((path(comparison,rid),{}),(path(rid,rid),{}),
                      (path(rid,comparison)+"&extra=1",{}),
                      (path(rid,comparison),{"Origin":"http://foreign.invalid"}),
                      (path(rid,comparison),{"Host":"foreign.invalid"})):
    try: get(route,headers)
    except HTTPError as exc:
        assert exc.code==503 and json.load(exc)["policy"]=="DENY"
    else: raise AssertionError("unverified request accepted")
assert get(path(rid,comparison))==result
print(json.dumps({"classification":"V3_GAMMA_E17_REAL_READBACK","result":"PASS",
                  "original_run_id":rid,"comparison_run_id":comparison,
                  "action_receipt_sha256":worker["action_receipt_sha256"],
                  "verification":result["verification"]["status"],
                  "projection_sha256":hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                  "negative_cases":5,"production_authorized":False},sort_keys=True))
