#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1126_MODE=READ_ONLY_FUNCTIONAL_INTERFACE_QUALIFICATION"
echo "FS1126_COMMIT=$(git -C "$ROOT" rev-parse --short HEAD)"
echo "FS1126_PRODUCTION_MUTATION=NONE"
echo "FS1126_REMEDIATION_EXECUTION=NONE"
echo "=== SERVICE NETWORK AND PORT INVENTORY ==="
python3 - <<'PY'
import json,subprocess
names=["core","worker","twin","intelligence","policy","evidence","prometheus","alertmanager","temporal","glpi"]
for suffix in names:
 name="aiops2-rebuild-"+suffix
 try:
  c=json.loads(subprocess.check_output(["docker","inspect",name],text=True))[0]
 except subprocess.CalledProcessError:
  print("SERVICE="+suffix+" STATUS=MISSING");continue
 state=c["State"]
 ports=list((c.get("NetworkSettings") or {}).get("Ports") or {})
 exposed=sorted((c.get("Config") or {}).get("ExposedPorts") or {})
 networks=sorted((c.get("NetworkSettings") or {}).get("Networks") or {})
 print("SERVICE=%s STATE=%s HEALTH=%s PORTS=%s NETWORKS=%s" % (
  suffix,state.get("Status"),(state.get("Health") or {}).get("Status","not-configured"),
  ",".join(ports or exposed) or "none",",".join(networks) or "none"))
PY
echo "=== REPOSITORY API AND TEST CANDIDATES ==="
python3 - "$ROOT" <<'PY'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
keywords=("openapi","swagger","api","incident","correlat","remediat","cmdb","e2e","integration")
skip={".git","node_modules",".venv","venv","dist","build","__pycache__"}
count=0
for p in root.rglob("*"):
 if not p.is_file() or any(part in skip for part in p.relative_to(root).parts):continue
 rel=str(p.relative_to(root))
 if len(rel)>180:continue
 if any(k in rel.lower() for k in keywords) and p.suffix.lower() in (".py",".ts",".tsx",".js",".json",".yaml",".yml",".sh"):
  print("CANDIDATE="+rel);count+=1
  if count>=100:break
print("CANDIDATE_COUNT_SHOWN="+str(count))
PY
echo "=== SAFE HTTP READ-ONLY PROBES ==="
for url in http://127.0.0.1:7777/ http://127.0.0.1:7777/explorer/cmdb http://127.0.0.1:8978/; do
 code="$(curl -sS -L --max-time 7 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
 echo "HTTP_PROBE=$url CODE=$code"
done
echo "=== QUALIFICATION MATRIX ==="
echo "INFRA_BASELINE=PASS_FROM_FS1125"
echo "INCIDENT_INGESTION=NOT_TESTED"
echo "EVENT_CORRELATION=NOT_TESTED"
echo "CMDB_ENRICHMENT=NOT_TESTED"
echo "AI_DIAGNOSIS=NOT_TESTED"
echo "POLICY_APPROVAL=NOT_TESTED"
echo "REMEDIATION_EXECUTION=NOT_TESTED"
echo "FS1126_RESULT=INTERFACE_INVENTORY_READY_FOR_TARGETED_TESTS"
