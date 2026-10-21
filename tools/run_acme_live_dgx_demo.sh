#!/usr/bin/env bash
# ACME connected demo: REAL DGX inference on SYNTHETIC input, no LIVE effects.
# Run only on the isolated Debian development Compose project.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env && -f compose.demo-local.yml && -f compose.llm-test.yml && -f compose.dgx-network.yml ]] || {
  echo "FAIL|missing_local_demo_configuration"; exit 2;
}
grep -q '^AIOPS_STACK_ID=aiops2-rebuild$' .env || { echo "FAIL|unexpected_stack"; exit 2; }
grep -q 'AIOPS_DEMO_LAUNCH_ENABLED' compose.demo-local.yml || { echo "FAIL|demo_disabled"; exit 2; }
DGX_BASE="${AIOPS_DGX_BASE_URL:-http://10.79.94.31:8000/v1}"
DGX_MODEL="${AIOPS_DGX_MODEL:-mistralai/Mistral-Small-4-119B-2603-NVFP4}"
[[ "$DGX_BASE" == http://10.79.94.31:8000/v1 ]] || { echo "FAIL|unapproved_dgx_url"; exit 2; }
mkdir -p reports
compose=(docker compose --env-file .env --profile test -f compose.yml -f compose.demo-local.yml -f compose.llm-test.yml -f compose.dgx-network.yml)
override="$(mktemp "$PWD/compose.dgx-demo.XXXXXX.yml")"
restore() {
  # Restore the known-good deterministic Intelligence provider on every exit.
  "${compose[@]}" up -d --no-deps --force-recreate aiops2-intelligence || echo "WARNING|restore_intelligence_failed"
  rm -f "$override"
}
trap restore EXIT
cat > "$override" <<EOF
services:
  aiops2-intelligence:
    environment:
      LLM_BASE_URL: "${DGX_BASE}"
      LLM_MODEL: "${DGX_MODEL}"
      LLM_TIMEOUT_SECONDS: "120"
      LLM_API_KEY: ""
EOF
echo "PHASE=DGX_PROVIDER_ACTIVATION"
"${compose[@]}" -f "$override" up -d --no-deps --force-recreate aiops2-intelligence
ready=0
for i in $(seq 1 45); do
  if docker exec aiops2-rebuild-intelligence python -c '
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:817/ready", timeout=3) as response:
    info = json.load(response)
assert info.get("status") == "ready"
assert info.get("provider_configured") is True
print("DGX_ADAPTER_READY=YES")
' 2>/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  echo "FAIL|dgx_adapter_not_ready_after_90s"
  docker logs --tail 35 aiops2-rebuild-intelligence 2>&1 | sed -E 's/(Bearer |token=|password=)[^ ]+/\\1[REDACTED]/Ig'
  exit 1
fi
echo "PHASE=SYNTHETIC_INCIDENT_REAL_INFERENCE"
# Keep token inside Portal. Use a unique temporary output path for this run.
launch="$(mktemp)"
trap 'rm -f "$launch"; restore' EXIT
docker exec aiops2-rebuild-portal python -c '
import os,json,urllib.request
token=os.environ["AIOPS_INTERNAL_TOKEN"]
req=urllib.request.Request("http://127.0.0.1:777/api/demo",data=b"{}",method="POST",headers={"Content-Type":"application/json","Authorization":"Bearer "+token})
with urllib.request.urlopen(req,timeout=30) as r: print(json.dumps(json.load(r)))
' > "$launch"
rid="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["run_id"])' "$launch")"
[[ "$rid" =~ ^RUN-[A-Za-z0-9_-]+$ ]] || { echo "FAIL|run_id_invalid"; exit 2; }
echo "DEMO_RUN_ID=$rid"
# Poll authenticated Portal API from inside Portal without displaying credentials.
for i in $(seq 1 240); do
  status="$(docker exec aiops2-rebuild-portal python -c '
import os,json,urllib.request,sys
rid=sys.argv[1]
req=urllib.request.Request("http://aiops2-core:810/api/runs/"+rid,headers={"Authorization":"Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"]})
with urllib.request.urlopen(req,timeout=10) as r: print(json.load(r)["run"]["status"])
' "$rid" 2>/dev/null || echo UNKNOWN)"
  [[ "$status" =~ ^(RESOLVED|BLOCKED|FAILED|CANCELLED)$ ]] && break
  sleep 2
done
echo "DEMO_RUN_STATUS=${status:-UNKNOWN}"
docker exec aiops2-rebuild-portal python -c '
import os,json,urllib.request,sys
rid=sys.argv[1]
req=urllib.request.Request("http://aiops2-core:810/api/runs/"+rid,headers={"Authorization":"Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"]})
with urllib.request.urlopen(req,timeout=10) as r: data=json.load(r)
print(json.dumps({"run_id":rid,"run_status":data["run"]["status"],"mode":data["run"]["mode"],"events":[{"stage":e.get("stage"),"event_type":e.get("event_type"),"status":e.get("status"),"decision":e.get("decision")} for e in data.get("events",[])],"live_effects_claim":"NOT_QUALIFIED"},ensure_ascii=False))
' "$rid" > "reports/acme-dgx-demo-$rid.json"
echo "DEMO_REPORT=reports/acme-dgx-demo-$rid.json"
echo "DEMO_VIEW=http://10.79.94.202:17777/demo-studio/run/$rid"
echo "NOTE=Real_Mistral_inference_with_synthetic_twin_evidence_not_production_diagnosis"
