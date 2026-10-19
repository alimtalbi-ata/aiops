#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
OUT=/home/aiops/aiops2-reconstruction/reports
mkdir -p "$OUT"; chmod 700 "$OUT"
REPORT="$OUT/runtime-inventory-$(date +%Y%m%d-%H%M%S).txt"
TMP="$REPORT.tmp"
{
  echo "AIOPS2 RUNTIME INVENTORY"; date --iso-8601=seconds; echo MODE=READ_ONLY
  echo "== ROOTS =="
  for p in /home/aiops/aiops2-v8-r4/00-Deployment /home/aiops/aiops-platform /home/aiops/.temporal-stage-20261017-171712 /home/aiops/exports/AIOPS-R33-LOGICAL-20261007-112249/03-SOURCES/V69/stack; do
    [[ -e "$p" ]] && echo "FOUND=$p" || echo "MISSING=$p"
  done
  echo "== CONTAINERS =="
  for c in aiops2_core aiops2_worker aiops2_policy aiops2_intelligence aiops2_integration aiops2_temporal aiops2_postgres aiops2_temporal_ui; do
    docker inspect "$c" --format 'NAME={{.Name}} IMAGE={{.Config.Image}} STATUS={{.State.Status}} PROJECT={{index .Config.Labels "com.docker.compose.project"}} SERVICE={{index .Config.Labels "com.docker.compose.service"}} WORKDIR={{index .Config.Labels "com.docker.compose.project.working_dir"}} CONFIG={{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>&1 || true
  done
  echo DATABASES_MODIFIED=NO; echo CONTAINERS_RESTARTED=NO; echo WORKFLOWS_STARTED=NO
} > "$TMP" 2>&1
mv "$TMP" "$REPORT"; chmod 600 "$REPORT"
sha256sum "$REPORT" > "$REPORT.sha256"
echo "REPORT=$REPORT"; echo "SHA256=$(cut -d' ' -f1 "$REPORT.sha256")"
