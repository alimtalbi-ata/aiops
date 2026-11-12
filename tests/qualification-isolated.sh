#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PROJECT="aiops2-isolated"
COMPOSE=(docker compose --env-file .env.isolated -p "$PROJECT" -f compose.isolated.yml)
fail() { echo "FAIL|$*" >&2; exit 1; }

for service in \
  aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy \
  aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal \
  aiops2-temporal-postgres aiops2-temporal aiops2-temporal-ui \
  aiops2-prometheus aiops2-grafana aiops2-alertmanager \
  aiops2-glpi-db aiops2-glpi aiops2-n8n; do
  id="$("${COMPOSE[@]}" ps -q "$service")"
  [[ -n "$id" ]] || fail "missing_container|$service"
  state="$(docker inspect -f '{{.State.Status}}' "$id")"
  [[ "$state" == "running" ]] || fail "container_not_running|$service|$state"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")"
  [[ "$health" == "none" || "$health" == "healthy" ]] || fail "container_unhealthy|$service|$health"
done

assert_loopback_port() {
  local service="$1" container_port="$2" host_port="$3" id
  id="$("${COMPOSE[@]}" ps -q "$service")"
  docker inspect "$id" | python3 -c '
import json,sys
data=json.load(sys.stdin)[0]
container_port=sys.argv[1]+"/tcp"
host_port=sys.argv[2]
bindings=(data.get("NetworkSettings",{}).get("Ports",{}).get(container_port) or [])
if len(bindings)!=1 or bindings[0].get("HostIp")!="127.0.0.1" or bindings[0].get("HostPort")!=host_port:
    raise SystemExit("FAIL|non_loopback_or_unexpected_binding|"+container_port)
' "$container_port" "$host_port" || fail "port_binding|$service|$host_port"
}
assert_loopback_port aiops2-portal 777 17777
assert_loopback_port aiops2-glpi 80 18080
assert_loopback_port aiops2-n8n 5678 15678
assert_loopback_port aiops2-prometheus 9090 19090
assert_loopback_port aiops2-grafana 3000 13000
assert_loopback_port aiops2-alertmanager 9093 19093

wait_http() {
  local url="$1" i
  for i in $(seq 1 90); do
    if curl --silent --show-error --fail --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  fail "http_health_timeout|$url"
}
wait_http http://127.0.0.1:17777/health
wait_http http://127.0.0.1:18080/
wait_http http://127.0.0.1:15678/healthz
wait_http http://127.0.0.1:19090/-/ready
wait_http http://127.0.0.1:13000/api/health
wait_http http://127.0.0.1:19093/-/ready
echo "ISOLATED_QUALIFICATION=PASS|containers=18|published_bind=127.0.0.1"
