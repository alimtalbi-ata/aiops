#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/backups/aiops2-$STAMP}"
mkdir -p "$OUT"; chmod 700 "$OUT"
docker compose --env-file .env exec -T aiops2-postgres pg_dump -U aiops -d aiops --format=custom > "$OUT/aiops.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_dump -U temporal -d temporal --format=custom > "$OUT/temporal.dump"
cp .env "$OUT/.env.private"; chmod 600 "$OUT/.env.private"
git rev-parse HEAD > "$OUT/git-head.txt" 2>/dev/null || echo unknown > "$OUT/git-head.txt"
sha256sum "$OUT/aiops.dump" "$OUT/temporal.dump" "$OUT/git-head.txt" > "$OUT/SHA256SUMS"
echo "BACKUP=$OUT"
echo 'WARNING: this directory contains credentials; encrypt and store offline. Never upload it to GitHub.'
