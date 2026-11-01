#!/usr/bin/env bash
# Read-only on-host DEV qualification. No secrets, no Docker mutations.
set -Eeuo pipefail
portal=aiops2-rebuild-portal
expected_project=aiops2-rebuild
status=PASS
check() { printf '%s=%s\n' "$1" "$2"; [[ "$2" == PASS ]] || status=FAIL; }
echo "AIOPS2_DEBIAN_RUNTIME_REPORT_V1"
echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if docker inspect "$portal" >/dev/null 2>&1; then
  project="$(docker inspect "$portal" --format '{{index .Config.Labels "com.docker.compose.project"}}')"
  health="$(docker inspect "$portal" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')"
  binding="$(docker inspect "$portal" --format '{{json .HostConfig.PortBindings}}')"
  [[ "$project" == "$expected_project" ]] && check compose_owner PASS || check compose_owner FAIL
  [[ "$health" == healthy ]] && check portal_health PASS || check portal_health FAIL
  [[ "$binding" == *'"HostPort":"7777"'* ]] && check portal_7777_binding PASS || check portal_7777_binding FAIL
else
  check portal_container FAIL
fi
if curl -fsS --max-time 10 http://127.0.0.1:7777/health |
   python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok" and d["component"]=="portal" and d["external_port"]==7777'; then
  check portal_http_7777 PASS
else
  check portal_http_7777 FAIL
fi
if docker inspect aiops2-portal-candidate-web-20261029 >/dev/null 2>&1; then
  echo "candidate_17778=PRESENT_REVIEW_REQUIRED"
else
  echo "candidate_17778=ABSENT"
fi
echo "overall=$status"
[[ "$status" == PASS ]]
