#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROJECT="aiops2-isolated"
ISOLATION_ID="aiops2-isolated"
ENV_FILE=".env.isolated"
COMPOSE=(docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f compose.yml -f compose.isolated.yml)

fail() { echo "HOLD|$*" >&2; exit 1; }
[[ "${EUID}" -eq 0 ]] || fail "run_as_authorized_operator_on_target_only"
[[ -f compose.yml && -f compose.isolated.yml ]] || fail "compose_files_missing"
command -v docker >/dev/null 2>&1 || fail "docker_missing"
command -v ss >/dev/null 2>&1 || fail "ss_missing"
command -v curl >/dev/null 2>&1 || fail "curl_missing"
docker compose version >/dev/null 2>&1 || fail "docker_compose_missing"

# Create a dedicated environment file. Never read or overwrite the standard .env.
if [[ ! -f "$ENV_FILE" ]]; then
  bash deploy/init-env.sh "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  sed -i "s/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=$PROJECT/" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
bash deploy/check-secrets.sh "$ENV_FILE"

env_value() {
  awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "$ENV_FILE"
}
[[ "$(env_value COMPOSE_PROJECT_NAME)" == "$PROJECT" ]] || fail "unexpected_compose_project_name"
[[ "$(env_value AIOPS_ISOLATION_ID)" == "$ISOLATION_ID" ]] || fail "unexpected_isolation_id"

FREE_KB="$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')"
(( FREE_KB > 8388608 )) || fail "disk_space_below_8GiB"
[[ "${RETIRE_LEGACY:-0}" != "1" ]] || fail "legacy_retirement_forbidden"

# Never adopt an existing project, volume or network.
if docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | grep -q .; then fail "project_containers_already_exist"; fi
for name in \
  "${ISOLATION_ID}_postgres_data" "${ISOLATION_ID}_temporal_postgres_data" \
  "${ISOLATION_ID}_prometheus_data" "${ISOLATION_ID}_grafana_data" \
  "${ISOLATION_ID}_glpi_db_data" "${ISOLATION_ID}_glpi_data" "${ISOLATION_ID}_n8n_data"; do
  if docker volume inspect "$name" >/dev/null 2>&1; then fail "volume_already_exists|$name"; fi
done
for name in \
  "${ISOLATION_ID}_public" "${ISOLATION_ID}_control" "${ISOLATION_ID}_data" \
  "${ISOLATION_ID}_execution" "${ISOLATION_ID}_temporal_data" \
  "${ISOLATION_ID}_integration" "${ISOLATION_ID}_observability"; do
  if docker network inspect "$name" >/dev/null 2>&1; then fail "network_already_exists|$name"; fi
done

# Ports must be free before Compose creates anything.
for port in 17777 18080 15678 19090 13000 19093; do
  if ss -H -ltn "sport = :$port" | grep -q .; then fail "host_port_in_use|$port"; fi
done

"${COMPOSE[@]}" config --quiet
# Strict offline mode: all runtime and application images must already exist locally.
# No image pull and no build is permitted by this installer.
while IFS= read -r image; do
  [[ -n "$image" ]] || continue
  docker image inspect "$image" >/dev/null 2>&1 || fail "image_not_preloaded|$image"
done < <("${COMPOSE[@]}" config --images)
for service in aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal; do
  docker image inspect "$PROJECT-$service" >/dev/null 2>&1 || fail "application_image_not_preloaded|$PROJECT-$service"
done

echo "PREFLIGHT=PASS|project=$PROJECT|mode=offline|published_ports=loopback_only"
"${COMPOSE[@]}" up -d --no-build --pull never
bash tests/qualification-isolated.sh
BASE_URL="http://127.0.0.1:17777" bash tests/synthetic-e2e.sh
echo "ISOLATED_INSTALL=PASS|project=$PROJECT"
