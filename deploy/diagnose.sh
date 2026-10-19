#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/reports/diagnostics-$STAMP}"
mkdir -p "$OUT"; chmod 700 "$OUT"
redact() { sed -E 's/(PASSWORD|TOKEN|API_KEY|ENCRYPTION_KEY)([=:][[:space:]]*)[^[:space:]]+/\1\2[REDACTED]/Ig'; }
{
 echo "timestamp_utc=$STAMP"
 echo "git_head=$(git rev-parse HEAD 2>/dev/null || echo unavailable)"
 echo "branch=$(git branch --show-current 2>/dev/null || echo unavailable)"
 docker --version 2>&1 || true
 docker compose version 2>&1 || true
} > "$OUT/host.txt"
docker compose --env-file .env ps --all > "$OUT/compose-ps.txt" 2>&1 || true
docker compose --env-file .env config --services > "$OUT/services.txt" 2>&1 || true
docker compose --env-file .env logs --no-color --tail=500 2>&1 | redact > "$OUT/logs-redacted.txt" || true
for name in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-prometheus aiops2-grafana aiops2-alertmanager aiops2-glpi aiops2-n8n; do
 docker inspect --format '{{.Name}} state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}} image={{.Config.Image}}' "$name" 2>/dev/null || echo "$name missing"
done > "$OUT/container-state.txt"
if [[ -f .env ]]; then bash deploy/check-secrets.sh .env > "$OUT/secret-check.txt" 2>&1 || true; fi
find "$OUT" -maxdepth 1 -type f -printf '%f %s bytes\n' > "$OUT/manifest.txt"
echo "DIAGNOSTICS=$OUT"
echo 'Review redacted logs before sharing; no .env file or database dump is included.'
