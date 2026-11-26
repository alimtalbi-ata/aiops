"""Run inside the existing V3 worker; never publishes a host port or acts."""
import hashlib
import json
import os
import re
import sys
import requests

assert os.environ.get("AIOPS_V3_BOUNDARY")=="1"
assert os.environ["CORE_URL"]=="http://core:810"
assert os.environ["TEMPORAL_ADDRESS"]=="temporal:7233"
report=json.load(sys.stdin)
assert report["classification"]=="V3_TEMPORAL_E17_LAB_RUNTIME"
assert report["result"]=="PASS" and report["production_authorized"] is False
rid=report["workflow_id"]
comparison=report["verification"]["comparison_run_id"]
assert all(re.fullmatch(r"RUN-[A-F0-9]{16}",x) for x in (rid,comparison))
base="http://127.0.0.1:815/api/v3/lab/e17/receipt/"
headers={"Authorization":"Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"]}
session=requests.Session()
session.trust_env=False
def get(r,auth):
    return session.get(base+r,headers=auth,timeout=20,allow_redirects=False)
assert get(rid,{}).status_code==401
assert get(rid,{"Authorization":"Bearer invalid"}).status_code==401
assert get("bad",headers).status_code==422
assert get(comparison,headers).status_code==404
boundary=sys.argv[1]
assert re.fullmatch(r"RUN-[A-F0-9]{16}",boundary) and boundary not in (rid,comparison)
assert get(boundary,headers).status_code==404
response=get(rid,headers)
response.raise_for_status()
actual=response.json()
expected={"classification":"V3_E17_WORKER_RECEIPT_READBACK","run_id":rid,
          "action_receipt":report["action_receipt"],"action_receipt_sha256":report["action_receipt_sha256"],
          "history_events":report["history_events"],"activities_completed":1,
          "operational_decision":"DENY","production_authorized":False,"core_business_stages_qualified":False}
assert actual==expected
assert hashlib.sha256(json.dumps(actual["action_receipt"],sort_keys=True,separators=(",",":")).encode()).hexdigest()==actual["action_receipt_sha256"]
assert get(rid,headers).json()==actual
print(json.dumps(actual,sort_keys=True))
