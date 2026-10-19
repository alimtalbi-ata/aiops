#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
MODE="${1:---plan}"
case "$MODE" in --plan|--apply) ;; *) echo 'Usage: deploy.sh [--plan|--apply]' >&2; exit 2 ;; esac
"$(dirname "$0")/preflight.sh"
PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' aiops2_core)
WORKDIR=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' aiops2_core)
FILES=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' aiops2_core)
IFS=',' read -r -a compose_files <<< "$FILES"
COMPOSE_ARGS=()
for f in "${compose_files[@]}"; do COMPOSE_ARGS+=(-f "$f"); done
SERVICES=$(cd "$WORKDIR" && docker compose "${COMPOSE_ARGS[@]}" config --services)
TARGETS=(core worker policy intelligence rag portal twin simulator evidence copilot integration)
SELECTED=()
for s in "${TARGETS[@]}"; do
  if grep -qx "$s" <<< "$SERVICES"; then SELECTED+=("$s"); fi
done
(("${#SELECTED[@]}" > 0)) || { echo 'DEPLOY=REFUSED: no expected application services in detected Compose' >&2; exit 3; }
printf 'COMPOSE_PROJECT=%s\nCOMPOSE_WORKDIR=%s\nSERVICES_TO_RECONCILE=%s\n' "$PROJECT" "$WORKDIR" "${SELECTED[*]}"
echo 'TEMPORAL_AND_DATABASE_SERVICES=EXCLUDED'
echo 'BUILD=DISABLED'
if [ "$MODE" = '--plan' ]; then echo 'DEPLOY=PLAN_ONLY'; echo 'No container or database was modified.'; exit 0; fi
[ "${AIOPS2_DEPLOY_APPROVED:-}" = YES ] || { echo 'DEPLOY=REFUSED: set AIOPS2_DEPLOY_APPROVED=YES only after human approval' >&2; exit 4; }
cd "$WORKDIR"
docker compose "${COMPOSE_ARGS[@]}" up -d --no-build --no-deps "${SELECTED[@]}"
docker compose "${COMPOSE_ARGS[@]}" ps
echo 'DEPLOY=COMMANDS_COMPLETED'
echo 'Note: no new image or code version was built.'
