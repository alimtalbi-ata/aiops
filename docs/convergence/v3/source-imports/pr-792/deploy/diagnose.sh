#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/reports/diagnostics-$STAMP}"
mkdir -p "$OUT"; chmod 700 "$OUT"
[[ -f .env ]] || { echo "FAIL|missing_env"; exit 2; }
STACK_ID="$(sed -n 's/^AIOPS_STACK_ID=//p' .env | head -1)"
STACK_ID="${STACK_ID:-aiops2}"
[[ "$STACK_ID" =~ ^[a-z][a-z0-9-]{2,28}$ ]] || { echo "FAIL|invalid_stack_id"; exit 2; }
PROJECT="$(docker compose --env-file .env config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["name"])')"
[[ "$PROJECT" == "$STACK_ID" ]] || { echo "FAIL|diagnostic_project_mismatch"; exit 3; }
redact() { python3 deploy/redact_logs.py .env; }
{
 echo "timestamp_utc=$STAMP"
 echo "git_head=$(git rev-parse HEAD 2>/dev/null || echo unavailable)"
 echo "branch=$(git branch --show-current 2>/dev/null || echo unavailable)"
 docker --version 2>&1 || true
 docker compose version 2>&1 || true
} > "$OUT/host.txt"
docker compose --env-file .env ps --all > "$OUT/compose-ps.txt" 2>&1 || true
docker compose --env-file .env config --services > "$OUT/services.txt" 2>&1 || true
if ! docker compose --env-file .env logs --no-color --tail=300 2>&1 | redact > "$OUT/logs-redacted.txt"; then
  rm -f "$OUT/logs-redacted.txt"
  echo "LOG_REDACTION=FAIL|logs_not_saved" > "$OUT/log-status.txt"
else
  echo "LOG_REDACTION=PASS" > "$OUT/log-status.txt"
fi
while IFS= read -r service; do
  [[ -n "$service" ]] || continue
  container="$(docker compose --env-file .env ps -aq "$service" | head -1)"
  if [[ -z "$container" ]]; then echo "$service missing"; continue; fi
  owner="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$container" 2>/dev/null || echo unavailable)"
  if [[ "$owner" != "$STACK_ID" ]]; then echo "$service FOREIGN_PROJECT"; continue; fi
  docker inspect --format '{{.Name}} state={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}} image={{.Config.Image}}' "$container" 2>/dev/null || echo "$service inspect_unavailable"
done < "$OUT/services.txt" > "$OUT/container-state.txt"
if [[ -f .env ]]; then bash deploy/check-secrets.sh .env > "$OUT/secret-check.txt" 2>&1 || true; fi
(
  cd "$OUT"
  find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name manifest.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
find "$OUT" -maxdepth 1 -type f -printf '%f %s bytes\n' > "$OUT/manifest.txt"
echo "DIAGNOSTICS=$OUT"
echo "DIAGNOSTIC_SCOPE=$STACK_ID|mutation=false|private=true"
echo 'Review redacted logs before sharing; no .env file or database dump is included.'
