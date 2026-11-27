"""Read the actual E17 receipt and independent Verify through GAMMA's HTTP API."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from urllib.error import HTTPError

origin,root=sys.argv[1:3]
assert sys.argv[3:] in ([],["product"],["product-container"])
container_profile=sys.argv[3:]==["product-container"]
if container_profile:
    assert origin=="http://127.0.0.1:18080"
name="temporal-e17-product" if sys.argv[3:] else "temporal-e17"
assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin)
assert int(origin.rsplit(":",1)[1]) not in (7770,7777,7790)
root=Path(root)
assert root==Path("/tmp/aiops-v3-rootless-ci")
report=json.loads((root/(name+".json")).read_text())
worker=json.loads((root/(name+"-worker-replay.json")).read_text())
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
try:
    result=get(path(rid,comparison))
except HTTPError as exc:
    raise SystemExit("E17_POSITIVE_HTTP_"+str(exc.code)) from None
def canonical_projection(value):
    # Evidence collections are unordered sets of immutable references. Preserve
    # every ID and digest, reject duplicate IDs, and compare all other fields exactly.
    from copy import deepcopy
    copy=deepcopy(value)
    for key in ("original_evidence","comparison_evidence"):
        refs=copy["verification"][key]
        assert isinstance(refs,list) and 1<=len(refs)<=20
        assert all(set(r)=={"evidence_id","payload_hash"} and
                   re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",r["evidence_id"]) and
                   re.fullmatch(r"[a-f0-9]{64}",r["payload_hash"]) for r in refs)
        assert len({r["evidence_id"] for r in refs})==len(refs)
        copy["verification"][key]=sorted(refs,key=lambda r:r["evidence_id"])
    return copy

expected={"classification":"SYNTHETIC_GAMMA_E17_VERIFIED_READBACK",
          "worker":worker,"verification":report["verification"],
          "operational_decision":"DENY","production_authorized":False,
          "tenant_acl_qualified":False,"core_business_stages_qualified":False}
actual=canonical_projection(result)
expected=canonical_projection(expected)
if actual!=expected:
    fields=[key for key in sorted(actual.keys()|expected.keys()) if actual.get(key)!=expected.get(key)]
    verify_fields=[key for key in sorted(actual["verification"].keys()|expected["verification"].keys())
                   if actual["verification"].get(key)!=expected["verification"].get(key)]
    raise AssertionError("E17 projection mismatch: fields="+str(fields)+" verification="+str(verify_fields))
print("E17 receipt, measured result and exact evidence reference sets match",file=sys.stderr)
for route,headers in ((path(comparison,rid),{}),(path(rid,rid),{}),
                      (path(rid,comparison)+"&extra=1",{}),
                      (path(rid,comparison),{"Origin":"http://foreign.invalid"}),
                      (path(rid,comparison),{"Host":"foreign.invalid"})):
    try: get(route,headers)
    except HTTPError as exc:
        expected_status=403 if container_profile and headers else 503
        if exc.code!=expected_status or json.load(exc).get("policy")!="DENY":
            raise SystemExit("E17_NEGATIVE_STATUS_"+str(exc.code)+"_EXPECTED_"+str(expected_status)) from None
    else: raise AssertionError("unverified request accepted")
assert canonical_projection(get(path(rid,comparison)))==actual
print(json.dumps({"classification":"V3_GAMMA_E17_REAL_READBACK","result":"PASS",
                  "original_run_id":rid,"comparison_run_id":comparison,
                  "action_receipt_sha256":worker["action_receipt_sha256"],
                  "verification":result["verification"]["status"],
                  "projection_sha256":hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                  "negative_cases":5,"production_authorized":False},sort_keys=True))
