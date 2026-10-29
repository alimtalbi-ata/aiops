#!/usr/bin/env bash
# Read-only smoke checks for the deployed AIOps2 Debian runtime.
# Never creates incidents/runs, writes Evidence, or changes containers.
set -Eeuo pipefail

fail() { echo "::error::$*"; exit 1; }

check_container() {
  local name="$1" state
  state="$(docker inspect "$name" --format '{{.State.Status}}' 2>/dev/null)" || fail "container missing: $name"
  [[ "$state" == "running" ]] || fail "container not running: $name ($state)"
  echo "PASS container/$name"
}

check_health() {
  local name="$1" port="$2" component="$3"
  docker exec "$name" python -c "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:${port}/health',timeout=8); d=json.load(r); assert d.get('status')=='ok' and d.get('component')=='${component}',d; print('PASS health/${component}: HTTP',r.status)" || fail "health endpoint failed: $name"
}

echo AIOPS2_RUNTIME_SMOKE=START
for name in aiops2-rebuild-core aiops2-rebuild-worker aiops2-rebuild-policy aiops2-rebuild-evidence; do check_container "$name"; done
check_health aiops2-rebuild-core 810 core
check_health aiops2-rebuild-worker 815 worker
check_health aiops2-rebuild-policy 813 policy
check_health aiops2-rebuild-evidence 812 evidence

echo '=== Core scenario contract ==='
docker exec aiops2-rebuild-core python -c 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:810/api/scenarios/SCN-GOLDEN-PAYMENT-P1",timeout=8)); s=d.get("scenario",{}); assert s.get("scenario_id")=="SCN-GOLDEN-PAYMENT-P1" and s.get("synthetic") is True,d; print("PASS scenario/SCN-GOLDEN-PAYMENT-P1 synthetic=true")' || fail 'Golden Payment scenario unavailable or not synthetic'

echo '=== Worker image and evidence timestamp contract ==='
image="$(docker inspect aiops2-rebuild-worker --format '{{.Config.Image}}')"
expected="${AIOPS_EXPECTED_WORKER_IMAGE:-aiops2-acme-candidate:worker-observed-at-fixed-20261030}"
[[ "$image" == "$expected" ]] || fail "unexpected worker image: $image (expected $expected)"
docker exec aiops2-rebuild-worker sh -c "grep -Fq \"'observed_at':observed\" /app/worker/main.py && ! grep -Fq \"'observed_at':None\" /app/worker/main.py" || fail 'Worker evidence observed_at contract failed'
echo PASS worker/evidence-observed-at
echo "PASS worker/image: $image"

echo '=== Temporal connectivity ==='
docker exec aiops2-rebuild-worker python -c 'import socket; s=socket.create_connection(("aiops2-temporal",7233),timeout=5); s.close(); print("PASS temporal/tcp-7233")' || fail 'Worker cannot reach Temporal at aiops2-temporal:7233'

echo AIOPS2_RUNTIME_SMOKE=PASS
