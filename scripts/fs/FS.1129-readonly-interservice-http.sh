#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1129_MODE=READ_ONLY_INTERSERVICE_HTTP_QUALIFICATION"
echo "FS1129_COMMIT=$(git -C "$ROOT" rev-parse --short HEAD)"
echo "FS1129_PRODUCTION_MUTATION=NONE"
echo "FS1129_AUTH_TOKENS=NOT_READ"
echo "FS1129_REMEDIATION=NOT_EXECUTED"
docker run --rm --network aiops2-rebuild-control python:3.12-slim python - <<'PY'
import json,urllib.request,urllib.error
checks=[
 ("CORE_HEALTH","aiops2-rebuild-core",810,"/health"),
 ("WORKER_HEALTH","aiops2-rebuild-worker",815,"/health"),
 ("TWIN_HEALTH","aiops2-rebuild-twin",811,"/health"),
 ("TWIN_SUMMARY","aiops2-rebuild-twin",811,"/api/twin/summary"),
 ("TWIN_QUALITY","aiops2-rebuild-twin",811,"/api/twin/acme-quality"),
 ("INTELLIGENCE_HEALTH","aiops2-rebuild-intelligence",817,"/health"),
 ("POLICY_HEALTH","aiops2-rebuild-policy",813,"/health"),
 ("EVIDENCE_HEALTH","aiops2-rebuild-evidence",812,"/health"),
 ("PROMETHEUS_READY","aiops2-rebuild-prometheus",9090,"/-/ready"),
]
for label,host,port,path in checks:
 url=f"http://{host}:{port}{path}"
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/json"}),timeout=6) as r:
   body=r.read(65536)
   status=r.status
  print(f"PROBE={label} HTTP={status}")
  if label=="TWIN_SUMMARY":
   try:
    data=json.loads(body)
    print("TWIN_SUMMARY_NODES=%s EDGES=%s"%(data.get("nodes","unknown"),data.get("edges","unknown")))
   except (ValueError,TypeError):print("TWIN_SUMMARY_PARSE=FAIL")
  if label=="TWIN_QUALITY":
   try:
    data=json.loads(body)
    print("TWIN_QUALITY_STATUS=%s ORPHAN_ENDPOINTS=%s ISOLATED_SERVICES=%s"%(data.get("quality_status","unknown"),len(data.get("orphan_edge_endpoints",[])),len(data.get("services_without_outgoing_relation",[]))))
   except (ValueError,TypeError):print("TWIN_QUALITY_PARSE=FAIL")
 except urllib.error.HTTPError as e:
  print(f"PROBE={label} HTTP={e.code} STATUS=HTTP_ERROR")
 except Exception as e:
  print(f"PROBE={label} STATUS=UNREACHABLE ERROR={type(e).__name__}")
PY
echo "FS1129_RESULT=READ_ONLY_PROBES_COMPLETE"
