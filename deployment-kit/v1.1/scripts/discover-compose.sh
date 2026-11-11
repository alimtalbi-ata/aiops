#!/usr/bin/env bash
# Read-only recovery helper. Does not print environment values or change containers.
set -Eeuo pipefail
umask 077
ROOT="${ROOT:-/home/aiops}"
OUT="${OUT:-/home/aiops/recovery/DB-BACKUP-20261019-193924/validation/compose-source-discovery}"
mkdir -p "$OUT"
chmod 700 "$OUT"
REPORT="$OUT/compose-source-discovery.txt"
{
  echo "DISCOVERY_TIME=$(date --iso-8601=seconds)"
  echo "HOST=$(hostname)"
  echo "MODE=READ_ONLY"
  echo "===== DOCKER COMPOSE LABELS ====="
  for c in aiops2_core aiops2_worker aiops2_temporal aiops2_postgres; do
    docker inspect "$c" --format 'container={{.Name}} status={{.State.Status}} project={{index .Config.Labels "com.docker.compose.project"}} working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} config_files={{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>&1 || true
  done
  echo "===== LABELED FILE EXISTENCE + HASH ====="
  for c in aiops2_core aiops2_worker aiops2_temporal aiops2_postgres; do
    files=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$c" 2>/dev/null || true)
    [ -n "$files" ] || continue
    IFS=',' read -r -a paths <<< "$files"
    for f in "${paths[@]}"; do
      if [ -f "$f" ]; then sha256sum "$f"; else echo "MISSING=$f"; fi
    done
  done
  echo "===== CANDIDATE COMPOSE FILES UNDER ROOT ====="
  find "$ROOT"     \( -path "$ROOT/recovery" -o -path "$ROOT/backups" -o -path "$ROOT/.git" -o -path "$ROOT/.venv" -o -path '*/node_modules' \) -prune -o     -type f \( -name 'compose.yml' -o -name 'compose.yaml' -o -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.*.yml' -o -name 'compose.*.yaml' \) -print 2>"$OUT/find-errors.txt" | sort
  echo "===== SHA256 OF CANDIDATES ====="
  find "$ROOT"     \( -path "$ROOT/recovery" -o -path "$ROOT/backups" -o -path "$ROOT/.git" -o -path "$ROOT/.venv" -o -path '*/node_modules' \) -prune -o     -type f \( -name 'compose.yml' -o -name 'compose.yaml' -o -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.*.yml' -o -name 'compose.*.yaml' \) -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum
  echo "===== SAFETY ====="
  echo "DATABASES_MODIFIED=NO"
  echo "WORKFLOWS_STARTED=NO"
  echo "CONTAINERS_RESTARTED=NO"
} 2>&1 | tee "$REPORT"
sha256sum "$REPORT" > "$REPORT.sha256"
echo "REPORT=$REPORT"
echo "REPORT_SHA256=$(cut -d' ' -f1 "$REPORT.sha256")"
