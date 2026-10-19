#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail(){ echo "PREFLIGHT=FAIL: $*" >&2; exit 2; }
command -v docker >/dev/null || fail 'docker CLI absent'
docker info >/dev/null 2>&1 || fail 'Docker daemon inaccessible'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose plugin absent'

for c in aiops2_core aiops2_worker aiops2_policy aiops2_intelligence aiops2_rag aiops2_portal aiops2_twin aiops2_simulator aiops2_evidence aiops2_copilot aiops2_integration aiops2_temporal aiops2_postgres; do
  docker inspect "$c" >/dev/null 2>&1 || fail "required container absent: $c"
  [ "$(docker inspect -f '{{.State.Running}}' "$c")" = true ] || fail "container not running: $c"
done

NET=$(docker inspect -f '{{json .NetworkSettings.Networks}}' aiops2_temporal)
case "$NET" in *'aiops2_temporal'*) ;; *) fail 'canonical Temporal server is not attached to aiops2_temporal' ;; esac

NS=$(docker exec aiops2_postgres sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d temporal -Atc "SELECT name FROM namespaces ORDER BY name"') || fail 'cannot read Temporal namespace catalog'
printf '%s\n' "$NS" | grep -qx 'default' || fail 'V2 Temporal namespace default not found'

QUEUE=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' aiops2_worker | grep -E '^(TASK_QUEUE|TEMPORAL_TASK_QUEUE)=' | head -1 || true)
[ -n "$QUEUE" ] || fail 'V2 worker task queue is not exposed in environment'

PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' aiops2_core)
WORKDIR=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' aiops2_core)
FILES=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' aiops2_core)
[ -n "$PROJECT" ] && [ -n "$WORKDIR" ] && [ -n "$FILES" ] || fail 'core Compose labels are incomplete'
IFS=',' read -r -a compose_files <<< "$FILES"
COMPOSE_ARGS=()
for f in "${compose_files[@]}"; do [ -f "$f" ] || fail "Compose file missing: $f"; COMPOSE_ARGS+=(-f "$f"); done
( cd "$WORKDIR" && docker compose "${COMPOSE_ARGS[@]}" config -q ) || fail 'invalid Compose configuration'

echo 'PREFLIGHT=PASS'
echo "COMPOSE_PROJECT=$PROJECT"
echo "COMPOSE_WORKDIR=$WORKDIR"
echo "COMPOSE_FILES=$FILES"
echo 'TEMPORAL_BACKEND=aiops2_temporal'
echo 'TEMPORAL_NAMESPACE=default'
echo "WORKER_QUEUE=$QUEUE"
echo 'DATABASES_MODIFIED=NO'
echo 'CONTAINERS_RESTARTED=NO'
