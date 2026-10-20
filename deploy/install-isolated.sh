#!/usr/bin/env bash
# Fresh, isolated reconstruction. Existing AIOps containers, networks, DBs and volumes are untouched.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
umask 077

STACK_ID="${AIOPS_ISOLATED_STACK_ID:-aiops2-rebuild}"
[[ "$STACK_ID" =~ ^[a-z][a-z0-9-]{2,28}$ && "$STACK_ID" != aiops2 ]] || {
  echo "FAIL|unsafe_isolated_stack_id"; exit 2;
}
if [[ -f .env ]] && ! grep -Fxq "AIOPS_STACK_ID=$STACK_ID" .env; then
  echo "FAIL|existing_env_targets_a_different_stack|do_not_overwrite"; exit 3
fi
bash deploy/init-env.sh

set_key() {
  local key="$1" value="$2"
  if grep -q "^$key=" .env; then
    sed -i "s|^$key=.*|$key=$value|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}
set_key AIOPS_STACK_ID "$STACK_ID"
set_key COMPOSE_PROJECT_NAME "$STACK_ID"
export AIOPS_STACK_ID="$STACK_ID" COMPOSE_PROJECT_NAME="$STACK_ID"
set_key AIOPS_BIND_IP "${AIOPS_ISOLATED_BIND_IP:-127.0.0.1}"
set_key AIOPS_PORTAL_HOST_PORT "${AIOPS_ISOLATED_PORTAL_PORT:-17777}"
set_key AIOPS_GLPI_HOST_PORT "${AIOPS_ISOLATED_GLPI_PORT:-18080}"
set_key AIOPS_N8N_HOST_PORT "${AIOPS_ISOLATED_N8N_PORT:-15678}"
set_key AIOPS_PROMETHEUS_HOST_PORT "${AIOPS_ISOLATED_PROMETHEUS_PORT:-19090}"
set_key AIOPS_GRAFANA_HOST_PORT "${AIOPS_ISOLATED_GRAFANA_PORT:-13000}"
set_key AIOPS_ALERTMANAGER_HOST_PORT "${AIOPS_ISOLATED_ALERTMANAGER_PORT:-19093}"
chmod 600 .env

# Validate identities, loopback publication and unique ports before touching Docker.
python3 deploy/plan_isolation.py --env .env --expected-stack "$STACK_ID"

if [[ "${1:-}" == "--configure-only" ]]; then
  echo "ISOLATED_CONFIG=PASS|stack_id=$STACK_ID|secrets_not_printed=true"
  exit 0
fi
[[ $# -eq 0 ]] || { echo "USAGE: bash deploy/install-isolated.sh [--configure-only]"; exit 2; }
command -v docker >/dev/null || { echo "FAIL|docker_missing"; exit 4; }
docker compose version >/dev/null || { echo "FAIL|docker_compose_missing"; exit 4; }

if docker inspect "$STACK_ID-core" >/dev/null 2>&1; then
  owner="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$STACK_ID-core")"
  [[ "$owner" == "$STACK_ID" ]] || { echo "FAIL|container_name_owned_by_other_project"; exit 5; }
else
  python3 deploy/plan_isolation.py --env .env --expected-stack "$STACK_ID" --probe-ports
fi

bash deploy/check-secrets.sh .env
docker compose --env-file .env config --quiet
docker compose --env-file .env config --format json |
  python3 deploy/plan_isolation.py --env .env --expected-stack "$STACK_ID" --compose-stdin
PORTAL_PORT="$(sed -n 's/^AIOPS_PORTAL_HOST_PORT=//p' .env | head -1)"
export BASE_URL="http://127.0.0.1:$PORTAL_PORT"
echo "ISOLATED_INSTALL_BEGIN|stack_id=$STACK_ID|no_destructive_legacy_actions=true"
RETIRE_LEGACY=0 bash deploy/install.sh
echo "ISOLATED_INSTALL=PASS|stack_id=$STACK_ID|portal_local=$BASE_URL"
echo "REMOTE_ACCESS_HINT=Use SSH port forwarding to local port $PORTAL_PORT"
