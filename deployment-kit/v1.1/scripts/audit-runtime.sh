#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
OUT="${1:-runtime-audit-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
chmod 700 "$OUT"
{
  echo "AUDIT_TIME=$(date --iso-8601=seconds)"
  echo "HOST=$(hostname)"
  echo "===== CONTAINERS ====="
  docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}' | grep -E 'aiops2|temporal' || true
  echo "===== CANONICAL LABELS ====="
  for c in aiops2_core aiops2_worker aiops2_temporal aiops2_postgres; do
    docker inspect "$c" --format 'name={{.Name}} status={{.State.Status}} image={{.Config.Image}} project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} config_files={{index .Config.Labels "com.docker.compose.project.config_files"}} networks={{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{end}}' 2>&1 || true
  done
  echo "===== TEMPORAL ROUTING ENV (NON-SECRET FIELDS ONLY) ====="
  for c in aiops2_worker; do
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$c" | grep -E '^(TEMPORAL_ADDRESS|TEMPORAL_NAMESPACE|TEMPORAL_TASK_QUEUE|TASK_QUEUE)=' || true
  done
  echo "===== TEMPORAL NAMESPACE CATALOG ====="
  docker exec aiops2_postgres sh -c 'psql -X -U "$POSTGRES_USER" -d temporal -Atc "SELECT name FROM namespaces ORDER BY name"' 2>&1 || true
  echo "DATABASES_MODIFIED=NO"
  echo "WORKFLOWS_STARTED=NO"
  echo "CONTAINERS_RESTARTED=NO"
} 2>&1 | tee "$OUT/runtime-audit.txt"
echo "AUDIT_REPORT=$OUT/runtime-audit.txt"
