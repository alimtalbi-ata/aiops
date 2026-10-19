#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=/home/aiops/aiops2; OUT="$ROOT/reports"
mkdir -p "$OUT";chmod 700 "$OUT"
REPORT="$OUT/diagnostic-$(date +%Y%m%d-%H%M%S).txt"
{ echo "AIOPS2 DIAGNOSTIC";date --iso-8601=seconds;echo MODE=READ_ONLY
 docker compose --env-file "$ROOT/.env" -f "$ROOT/00-Deployment/compose.yml" ps 2>&1 || true
 echo;curl -sS --max-time 3 http://127.0.0.1:18080/health 2>&1 || true
 echo;curl -sS --max-time 3 http://127.0.0.1:18080/ready 2>&1 || true
 echo;df -h /home/aiops;free -h
 docker compose --env-file "$ROOT/.env" -f "$ROOT/00-Deployment/compose.yml" logs --no-color --tail=150 2>&1 || true
 echo DATABASE_MODIFIED=NO;echo CONTAINERS_RESTARTED=NO; } > "$REPORT"
chmod 600 "$REPORT";sha256sum "$REPORT" > "$REPORT.sha256";echo "REPORT=$REPORT"